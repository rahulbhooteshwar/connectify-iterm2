#!/usr/bin/env python3
"""
Connectify - SSH Session Manager for iTerm2
A utility to manage and launch SSH sessions with credential storage and iTerm2 profile support

Built with ❤️ by RB
"""

import json
import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
import threading
import glob

import iterm_profiles
import ssh_session
import terminals

# Import version info
try:
    from version import VERSION, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    BUILD_DATE = "unknown"

# Password logins have to allow keyboard-interactive as well as the "password"
# method: plenty of servers (anything with PAM in the path) only advertise
# keyboard-interactive, and asking for `password` alone makes ssh give up with
# "Permission denied (keyboard-interactive)" without ever prompting.
PASSWORD_AUTH_OPTION = "PreferredAuthentications=password,keyboard-interactive"

# The option Connectify used to write, before that was understood
LEGACY_PASSWORD_AUTH_OPTION = "PreferredAuthentications=password"

# Default SSH "-o" options applied per authentication method when a host does
# not explicitly define its own `ssh_options` (kept for backward compatibility
# with hosts created before options were configurable from the UI).
DEFAULT_SSH_OPTIONS = {
    'password': [
        PASSWORD_AUTH_OPTION,
        "PubkeyAuthentication=no",
    ],
    'key': [
        "PreferredAuthentications=publickey",
        "PasswordAuthentication=no",
    ],
}


# Tile themes offered in the UI. "default" is the neutral tile. This list and
# ui/src/lib/themes.ts must agree - there is a test that compares them.
HOST_THEMES = ['default', 'red', 'orange', 'amber', 'green', 'teal', 'blue', 'violet', 'pink']
DEFAULT_HOST_THEME = 'default'


def normalize_theme(value):
    """Coerce a stored theme to one Connectify knows about."""
    theme = str(value or '').strip().lower()
    return theme if theme in HOST_THEMES else DEFAULT_HOST_THEME


def normalize_group(value):
    """Normalize a host's group; empty/missing means "ungrouped"."""
    return str(value or '').strip()


def group_hosts(hosts, order_key=None):
    """Split hosts into ``(groups, ungrouped)``.

    ``groups`` maps group name -> hosts. ``order_key`` decides the order they
    come back in - the user's arrangement, when there is one. Without it they
    are alphabetical (case-insensitive), which is what an unconfigured install
    gets. Hosts without a group are returned separately and rendered as-is by
    the callers.
    """
    groups = {}
    ungrouped = []

    for host in hosts:
        group = normalize_group(host.get('group'))
        if group:
            groups.setdefault(group, []).append(host)
        else:
            ungrouped.append(host)

    key = order_key or (lambda name: name.lower())
    ordered = {name: groups[name] for name in sorted(groups, key=key)}
    return ordered, ungrouped


def resolve_ssh_verbosity(host):
    """How chatty ssh should be for this host (0-3).

    Separate from `ssh_options` because -v is a flag, not an `-o` option.
    """
    return ssh_session.normalize_verbosity(host.get('ssh_verbosity'))


def resolve_ssh_options(host):
    """Resolve the list of SSH `-o` options for a host.

    Uses the host's explicit `ssh_options` when present (including an empty
    list, which means "no extra options"), otherwise falls back to the
    auth-method defaults for hosts that predate configurable options.
    """
    options = host.get('ssh_options')
    if options is None:
        auth_method = host.get('auth_method', 'password')
        return list(DEFAULT_SSH_OPTIONS.get(auth_method, []))
    return list(options)

class SSHManager:
    # Class-level lock to serialize terminal tab launches and prevent race
    # conditions when multiple connections are launched simultaneously
    _terminal_launch_lock = threading.Lock()

    # Kept under the old name for anything still reaching for it
    _iterm_launch_lock = _terminal_launch_lock

    # When several sessions are launched at once, give the terminal a beat
    # between tabs - it drops requests that arrive while it is still creating one
    _last_launch_at = 0.0
    LAUNCH_SETTLE_SECONDS = 0.35

    def __init__(self, config_file="~/.connectify/hosts.json", debug=False):
        self.config_file = Path(config_file).expanduser()
        self.old_config_file = Path("~/.ssh_manager_config.json").expanduser()
        # Enable debug via --debug flag or CONNECTIFY_DEBUG env var
        self.debug = debug or os.environ.get('CONNECTIFY_DEBUG', '').lower() in ('1', 'true', 'yes')
        
        # Migrate from old config location if needed
        self.migrate_old_config()
        
        self.config = self.load_config()

        # Which terminal sessions open in. Resolved once: detection shells out
        # to osascript, and this sits on the launch path.
        self.terminal, self.terminal_reason = terminals.resolve(
            self.config.get('terminal'), quiet=not self.debug)

        # Drop pre-vault fields from the host list (see the method for why)
        self.clean_legacy_host_fields()
        self.modernize_ssh_options()

        # Make sure the iTerm2 profiles shipped with Connectify are present.
        # Runs once per version (tracked by a marker file), so upgrades pick up
        # profile changes without re-running the installer.
        self.ensure_iterm_profiles()

        # Start background cleanup of old temp password files
        self.cleanup_old_temp_files()

    def ensure_iterm_profiles(self):
        """Install the bundled iTerm2 profiles if they are not in place yet.

        Skipped entirely when sessions open in something other than iTerm2 -
        creating its DynamicProfiles folder on a machine that has no iTerm2
        would leave litter for an app that will never read it.
        """
        if not self.terminal.supports_profiles:
            if self.debug:
                print(f"DEBUG: profile install skipped - sessions open in "
                      f"{self.terminal.display_name}")
            return

        try:
            result = iterm_profiles.ensure_profiles_installed(VERSION, quiet=True)
        except Exception as e:
            if self.debug:
                print(f"DEBUG: Profile installation skipped: {e}")
            return

        if not result:
            return

        changed = result.get('installed', []) + result.get('updated', [])
        if changed:
            names = ", ".join(Path(name).stem for name in changed)
            print(f"🎨 Installed Connectify iTerm2 profiles: {names}")
        for error in result.get('errors', []):
            print(f"⚠️  Could not install iTerm2 profile - {error}")

    def migrate_old_config(self):
        """Migrate from old config location to new location"""
        # Only migrate if old exists and new doesn't
        if self.old_config_file.exists() and not self.config_file.exists():
            print("🔄 Migrating configuration to new location...")
            print(f"   Old: {self.old_config_file}")
            print(f"   New: {self.config_file}")
            
            try:
                # Create new config directory
                os.makedirs(self.config_file.parent, exist_ok=True)
                
                # Copy old config to new location
                with open(self.old_config_file, 'r') as f:
                    old_config = json.load(f)
                
                with open(self.config_file, 'w') as f:
                    json.dump(old_config, f, indent=2, ensure_ascii=False)
                
                # Remove old config file
                os.remove(self.old_config_file)
                
                print("✅ Configuration migrated successfully!")
                print(f"   Your hosts are now in: {self.config_file}")
                print()
            except Exception as e:
                print(f"⚠️  Warning: Could not migrate config: {e}")
                print(f"   Please manually move {self.old_config_file} to {self.config_file}")
                print()

    def load_config(self):
        """Load SSH configuration from JSON file"""
        if not self.config_file.exists():
            self.create_sample_config()

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading config file: {e}")
            print(f"Please check {self.config_file}")
            sys.exit(1)

    def create_sample_config(self):
        """Create a sample configuration file"""
        sample_config = {
            "hosts": [
                {
                    "name": "Production Server",
                    "hostname": "prod.example.com",
                    "username": "admin",
                    "port": 22,
                    "credential": "",
                    "iterm_profile": "connectify-PROD",
                    "group": "Production",
                    "theme": "red",
                    "tags": ["production", "web"]
                },
                {
                    "name": "Dev Server",
                    "hostname": "dev.example.com",
                    "username": "developer",
                    "port": 2222,
                    "credential": "",
                    "iterm_profile": "connectify-NONPROD",
                    "group": "Development",
                    "theme": "green",
                    "tags": ["development", "testing"]
                }
            ]
        }

        os.makedirs(self.config_file.parent, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(sample_config, f, indent=2, ensure_ascii=False)

        print(f"Created sample configuration at {self.config_file}")
        print("Please edit this file to add your SSH hosts.")

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get_host(self, host_name):
        """Get host details by name"""
        hosts = self.config.get('hosts', [])
        for host in hosts:
            if host['name'] == host_name:
                return host
        return None

    def add_host_programmatic(self, host_data):
        """Add a new host programmatically"""
        # Check if host with same name exists
        if self.get_host(host_data['name']):
            raise ValueError(f"Host with name '{host_data['name']}' already exists")

        self.config.setdefault('hosts', []).append(host_data)
        self.save_config()
        return True

    def update_host(self, original_name, host_data):
        """Update an existing host"""
        hosts = self.config.get('hosts', [])
        for i, host in enumerate(hosts):
            if host['name'] == original_name:
                # If name is changing, check for collision
                if original_name != host_data['name'] and self.get_host(host_data['name']):
                    raise ValueError(f"Host with name '{host_data['name']}' already exists")

                hosts[i] = host_data
                self.save_config()
                return True
        raise ValueError(f"Host '{original_name}' not found")

    def delete_host(self, host_name):
        """Delete a host by name"""
        hosts = self.config.get('hosts', [])
        initial_len = len(hosts)
        self.config['hosts'] = [h for h in hosts if h['name'] != host_name]

        if len(self.config['hosts']) < initial_len:
            self.save_config()
            return True
        raise ValueError(f"Host '{host_name}' not found")

    def cleanup_old_temp_files(self):
        """Tidy up scratch files in the background (non-blocking).

        Two things to sweep: leftover session directories from sessions that
        were killed before their launcher could clean up, and the password
        files the pre-vault implementation used to drop in $HOME (nothing
        creates those any more, so every one of them is stale).
        """
        def cleanup_worker():
            try:
                ssh_session.sweep_runtime_dir()

                legacy_files = glob.glob(str(Path.home() / ".ssh_pass_*"))
                for path in legacy_files:
                    try:
                        Path(path).unlink()
                    except OSError:
                        pass

                if legacy_files:
                    print(f"🧹 Removed {len(legacy_files)} leftover password file(s) "
                          f"from the pre-vault version")
            except Exception:
                # Background housekeeping must never break a launch
                pass

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    # Sweeping walks a handful of directories, but there is no point doing it
    # on every keystroke either
    _last_sweep_at = 0.0
    _sweep_lock = threading.Lock()
    SWEEP_INTERVAL_SECONDS = 30

    @classmethod
    def sweep_session_files(cls, force=False):
        """Clear session directories left behind by tabs that were killed.

        A session cleans up after itself when ssh exits; this is for the ones
        that never got the chance. Runs in the background so nothing waits on
        it, and rate-limited so calling it from every page load and every
        launch costs nothing.
        """
        now = time.time()
        with cls._sweep_lock:
            if not force and now - cls._last_sweep_at < cls.SWEEP_INTERVAL_SECONDS:
                return False
            cls._last_sweep_at = now

        def worker():
            try:
                ssh_session.sweep_runtime_dir()
            except Exception:
                # Housekeeping must never break a launch or a page load
                pass

        threading.Thread(target=worker, daemon=True).start()
        return True

    def filter_hosts(self, filter_term=None):
        """Filter hosts based on search term"""
        hosts = self.config.get('hosts', [])

        if not filter_term:
            return hosts

        filter_term = filter_term.lower()
        filtered_hosts = []

        for host in hosts:
            # Search in name, group and tags only (excluding hostname)
            search_fields = [
                host.get('name', '').lower(),
                normalize_group(host.get('group')).lower(),
                ' '.join(host.get('tags', [])).lower()
            ]

            if any(filter_term in field for field in search_fields):
                filtered_hosts.append(host)

        return filtered_hosts

    def launch_session(self, host, credential=None):
        """Launch a terminal session for a host, using its vault credential.

        Everything here is terminal-agnostic: the session is prepared as a
        self-contained script and handed to whichever backend ``terminals``
        resolved. Any password or key passphrase reaches ssh through an askpass
        helper reading a private FIFO, so it is never written to disk, never
        passed on a command line, and sshpass is not involved - and that holds
        whichever terminal opens the tab.
        """
        # Tidy up anything a previous session left behind before adding one
        self.sweep_session_files()

        terminal = self.terminal
        # Only iTerm2 has profiles; the Terminal backend ignores the argument
        profile = host.get('iterm_profile', 'Default')
        login = ssh_session.effective_username(host, credential)
        host_name = host.get('name') or (
            f"{login}@{host['hostname']}" if login else host['hostname']
        )
        print(f"🚀 Launching {host_name} session...")

        terminal.ensure_running()

        credential = credential or {}
        if credential.get('type') == 'password' and not credential.get('password'):
            print(f"⚠️  Credential '{credential.get('name')}' has no password stored")
            print(f"⚠️  Fix it in the Vault and try again")
            raise ValueError(f"Password required for {host_name} but missing from the vault")

        session = ssh_session.prepare_session(
            host, credential,
            ssh_options=resolve_ssh_options(host),
            verbosity=resolve_ssh_verbosity(host),
        )

        if self.debug:
            print(f"DEBUG: terminal: {terminal.display_name} ({self.terminal_reason})")
            print(f"DEBUG: launcher: {session.launcher}")
            print(f"DEBUG: secret channel: {'yes' if session.channel else 'no'}")

        # Serialize the whole launch. Two AppleScripts creating tabs at the
        # same moment race over the terminal's "current window", and a user
        # switching tabs mid-launch used to be enough to lose a session.
        with SSHManager._terminal_launch_lock:
            # Give the terminal a moment to settle after the previous tab,
            # otherwise rapid-fire launches can outrun it
            since_last = time.time() - SSHManager._last_launch_at
            if since_last < self.LAUNCH_SETTLE_SECONDS:
                time.sleep(self.LAUNCH_SETTLE_SECONDS - since_last)

            if not terminal.ensure_running():
                session.cleanup()
                raise RuntimeError(
                    f"{terminal.display_name} is not running and could not be started")

            try:
                session_id = terminal.open_session(
                    session.command, host_name, profile, debug=self.debug)
            except terminals.TerminalLaunchError as e:
                SSHManager._last_launch_at = time.time()
                session.cleanup()

                print(f"✗ Could not open a session in {terminal.display_name}")
                print(f"   Last error: {e}")
                print(f"")
                print(f"💡 Troubleshooting tips:")
                print(f"   1. Make sure {terminal.display_name} can be launched")
                for i, line in enumerate(terminal.permission_hint()):
                    print(f"   2. {line}" if i == 0 else f"      {line}")
                print(f"   3. Try running {terminal.display_name} manually first")
                raise RuntimeError(
                    f"Could not open a session in {terminal.display_name}: {e}")

            SSHManager._last_launch_at = time.time()
            print(f"✅ Session launched ({session_id})")
            return True

    # The name this has always been called by, from the API and the tests
    launch_iterm_session = launch_session

    # Fields that predate the credentials vault. They described how to
    # authenticate; that now lives on the credential, so they are stripped on
    # startup rather than lingering as a second, stale source of truth.
    LEGACY_HOST_FIELDS = ('auth_method', 'ssh_key_path', 'password')

    def clean_legacy_host_fields(self):
        """Remove pre-vault authentication fields from hosts.json.

        The SSH options a host uses to be given by its auth method, so those
        are materialised first - otherwise dropping `auth_method` would
        silently change how an existing host connects. Every host ends up with
        a `credential` field, empty until one is picked in the UI.
        """
        changed = 0

        for host in self.config.get('hosts', []):
            touched = False

            if host.get('ssh_options') is None:
                defaults = DEFAULT_SSH_OPTIONS.get(host.get('auth_method', 'password'))
                if defaults:
                    host['ssh_options'] = list(defaults)
                    touched = True

            for field in self.LEGACY_HOST_FIELDS:
                if field in host:
                    del host[field]
                    touched = True

            if 'credential' not in host:
                host['credential'] = ''
                touched = True

            changed += 1 if touched else 0

        if changed:
            self.save_config()
            print(f"🧹 Cleaned pre-vault fields from {changed} host(s) - "
                  f"assign credentials in the Vault")

        return changed

    def modernize_ssh_options(self):
        """Let password logins use keyboard-interactive too.

        Hosts saved by an earlier version carry a bare
        `PreferredAuthentications=password`, which servers that only offer
        keyboard-interactive reject outright - ssh never even asks for the
        password. Rewriting it on startup fixes those hosts without the user
        having to know why they broke.
        """
        changed = 0

        for host in self.config.get('hosts', []):
            options = host.get('ssh_options')
            if not options or LEGACY_PASSWORD_AUTH_OPTION not in options:
                continue
            host['ssh_options'] = [
                PASSWORD_AUTH_OPTION if option == LEGACY_PASSWORD_AUTH_OPTION else option
                for option in options
            ]
            changed += 1

        if changed:
            self.save_config()
            print(f"🔑 Allowed keyboard-interactive password auth on {changed} host(s)")

        return changed

    def hosts_using_credential(self, credential_name):
        """Names of hosts referencing a credential (case-insensitive)."""
        wanted = str(credential_name or '').strip().lower()
        return [
            host.get('name')
            for host in self.config.get('hosts', [])
            if str(host.get('credential') or '').strip().lower() == wanted
        ]

    def rename_credential_references(self, old_name, new_name):
        """Keep host associations pointing at a renamed credential."""
        if old_name == new_name:
            return 0

        wanted = str(old_name or '').strip().lower()
        changed = 0
        for host in self.config.get('hosts', []):
            if str(host.get('credential') or '').strip().lower() == wanted:
                host['credential'] = new_name
                changed += 1
        if changed:
            self.save_config()
        return changed


def main():
    """Entry point for running the web UI server directly.

    The user-facing CLI lives in connectify.py; this module is the SSH engine
    behind the web UI and only needs to be able to start the server.
    """
    parser = argparse.ArgumentParser(
        prog='connectify',
        description="Connectify - SSH Session Manager for iTerm2 (web UI server)",
    )
    parser.add_argument('--version', action='store_true', help='Show version information')
    parser.add_argument('--config', help='Path to config file', default='~/.connectify/hosts.json')
    parser.add_argument('--ui', action='store_true', help='Launch the web interface (default)')
    parser.add_argument('--port', type=int, default=7860, help='Port for the web interface (default: 7860)')
    parser.add_argument('--share', action='store_true', help='Bind to 0.0.0.0 instead of localhost')
    parser.add_argument('--silent', action='store_true',
                        help='Run the web interface in background mode (fixed port 7890, no browser)')

    args = parser.parse_args()

    if args.version:
        print(f"Connectify v{VERSION}")
        print(f"Build: {BUILD_DATE}")
        return

    # Show initialization message on first run
    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print("⏳ First run initialization (this may take a moment)...")
        print()

    try:
        from api_server import launch_api_server
    except ImportError as e:
        print("❌ Web interface dependencies not installed.")
        print(f"Missing: {e}")
        print("Please run: uv sync")
        sys.exit(1)

    try:
        if args.silent:
            # Background mode: fixed port, no browser
            print("🔇 Starting Connectify web server in silent mode...")
            print("🌐 Server will run on http://localhost:7890")
            print("📋 Use Ctrl+C to stop the server")
            launch_api_server(args.config, 7890, "127.0.0.1", silent=True)
        else:
            print("🌐 Starting Connectify web interface...")
            print(f"🚀 Server will be available at http://localhost:{args.port}")
            if not args.share:
                # Open the browser once the server is up
                import webbrowser

                def open_browser():
                    time.sleep(1.5)
                    webbrowser.open(f"http://localhost:{args.port}")

                threading.Thread(target=open_browser, daemon=True).start()

            launch_api_server(args.config, args.port, "0.0.0.0" if args.share else "127.0.0.1", silent=False)
    except Exception as e:
        print(f"❌ Error launching web interface: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
