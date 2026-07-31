#!/usr/bin/env python3
"""
Connectify - SSH Session Manager for iTerm2
A utility to manage and launch SSH sessions with credential storage and iTerm2 profile support

Built with ❤️ by RB (Rahul Bhooteshwar)
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

# Import version info
try:
    from version import VERSION, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    BUILD_DATE = "unknown"

# Default SSH "-o" options applied per authentication method when a host does
# not explicitly define its own `ssh_options` (kept for backward compatibility
# with hosts created before options were configurable from the UI).
DEFAULT_SSH_OPTIONS = {
    'password': [
        "PreferredAuthentications=password",
        "PubkeyAuthentication=no",
    ],
    'key': [
        "PreferredAuthentications=publickey",
        "PasswordAuthentication=no",
    ],
}


# Tile themes offered in the UI. "default" is the neutral grey/black tile.
HOST_THEMES = ['default', 'red', 'green', 'orange']
DEFAULT_HOST_THEME = 'default'


def normalize_theme(value):
    """Coerce a stored theme to one Connectify knows about."""
    theme = str(value or '').strip().lower()
    return theme if theme in HOST_THEMES else DEFAULT_HOST_THEME


def normalize_group(value):
    """Normalize a host's group; empty/missing means "ungrouped"."""
    return str(value or '').strip()


def group_hosts(hosts):
    """Split hosts into ``(groups, ungrouped)``.

    ``groups`` maps group name -> hosts, ordered alphabetically
    (case-insensitive). Hosts without a group are returned separately and
    rendered as-is by the callers.
    """
    groups = {}
    ungrouped = []

    for host in hosts:
        group = normalize_group(host.get('group'))
        if group:
            groups.setdefault(group, []).append(host)
        else:
            ungrouped.append(host)

    ordered = {name: groups[name] for name in sorted(groups, key=str.lower)}
    return ordered, ungrouped


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
    # Class-level lock to serialize iTerm2 tab launches and prevent race conditions
    # when multiple connections are launched simultaneously
    _iterm_launch_lock = threading.Lock()

    def __init__(self, config_file="~/.connectify/hosts.json", debug=False):
        self.config_file = Path(config_file).expanduser()
        self.old_config_file = Path("~/.ssh_manager_config.json").expanduser()
        # Enable debug via --debug flag or CONNECTIFY_DEBUG env var
        self.debug = debug or os.environ.get('CONNECTIFY_DEBUG', '').lower() in ('1', 'true', 'yes')
        
        # Migrate from old config location if needed
        self.migrate_old_config()
        
        self.config = self.load_config()

        # Drop pre-vault fields from the host list (see the method for why)
        self.clean_legacy_host_fields()

        # Make sure the iTerm2 profiles shipped with Connectify are present.
        # Runs once per version (tracked by a marker file), so upgrades pick up
        # profile changes without re-running the installer.
        self.ensure_iterm_profiles()

        # Start background cleanup of old temp password files
        self.cleanup_old_temp_files()

    def ensure_iterm_profiles(self):
        """Install the bundled iTerm2 profiles if they are not in place yet."""
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

    def _ensure_iterm_running(self):
        """Ensure iTerm2 is running, launch it if not"""
        try:
            # Check if iTerm2 is running
            check_script = '''
            tell application "System Events"
                if exists (processes where name is "iTerm") then
                    return "running"
                else
                    return "not_running"
                end if
            end tell
            '''

            result = subprocess.run(['osascript', '-e', check_script],
                                  capture_output=True, text=True, check=True)

            if result.stdout.strip() == "not_running":
                print("📱 iTerm2 not running, launching it now...")

                # Try multiple methods to launch iTerm2
                launch_success = False

                # Method 1: AppleScript
                try:
                    launch_script = '''
                    tell application "iTerm"
                        activate
                    end tell
                    '''
                    subprocess.run(['osascript', '-e', launch_script], check=True, capture_output=True, text=True)
                    launch_success = True
                    print("✅ iTerm2 launched via AppleScript")
                except subprocess.CalledProcessError:
                    pass

                # Method 2: open command
                if not launch_success:
                    try:
                        subprocess.run(['open', '-a', 'iTerm'], check=True, capture_output=True, text=True)
                        launch_success = True
                        print("✅ iTerm2 launched via 'open' command")
                    except subprocess.CalledProcessError:
                        pass

                if not launch_success:
                    print("⚠️  Warning: Could not launch iTerm2. Make sure it's installed.")
                    print("   You can install it from: https://iterm2.com/downloads.html")
                    return False

                # Wait longer for iTerm2 to fully start
                print("   Waiting for iTerm2 to initialize...")
                time.sleep(3)
                return True
            else:
                # iTerm2 is already running
                return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            print(f"⚠️  Error checking iTerm2 status: {error_msg}")
            print("   Attempting to launch iTerm2 anyway...")
            try:
                subprocess.run(['open', '-a', 'iTerm'], check=True, capture_output=True, text=True)
                time.sleep(3)
                print("✅ iTerm2 launched")
                return True
            except subprocess.CalledProcessError:
                print("❌ Could not launch iTerm2")
                return False
        except Exception as e:
            print(f"⚠️  Unexpected error: {e}")
            return False

    def launch_iterm_session(self, host, credential=None):
        """Launch an iTerm2 session for a host, using its vault credential.

        The session is started as iTerm2's session *command*, so no shell runs
        it: the command never appears in the tab or in the shell history. Any
        password or key passphrase reaches ssh through an askpass helper
        reading a private FIFO, so it is never written to disk, never passed on
        a command line, and sshpass is not involved.
        """
        iterm_profile = host.get('iterm_profile', 'Default')
        host_name = host.get('name', f"{host['username']}@{host['hostname']}")
        print(f"🚀 Launching {host_name} session...")

        self._ensure_iterm_running()

        credential = credential or {}
        if credential.get('type') == 'password' and not credential.get('password'):
            print(f"⚠️  Credential '{credential.get('name')}' has no password stored")
            print(f"⚠️  Fix it in the Vault and try again")
            raise ValueError(f"Password required for {host_name} but missing from the vault")

        session = ssh_session.prepare_session(
            host, credential, ssh_options=resolve_ssh_options(host)
        )

        if self.debug:
            print(f"DEBUG: launcher: {session.launcher}")
            print(f"DEBUG: secret channel: {'yes' if session.channel else 'no'}")

        escaped_host_name = host_name.replace('\\', '\\\\').replace('"', '\\"')
        escaped_command = session.command.replace('\\', '\\\\').replace('"', '\\"')

        def create_applescript(profile_name):
            """AppleScript that opens a tab running the launcher directly.

            Explicit tab/window references avoid races when several sessions
            are launched at once, and passing the launcher as the session's
            command means nothing is ever typed into a shell.
            """
            return f'''
            tell application "iTerm"
                activate
                if (count of windows) = 0 then
                    set newWindow to (create window with profile "{profile_name}" command "{escaped_command}")
                    set targetSession to current session of newWindow
                else
                    tell current window
                        set newTab to (create tab with profile "{profile_name}" command "{escaped_command}")
                        set targetSession to current session of newTab
                    end tell
                end if
                tell targetSession
                    set name to "{escaped_host_name}"
                end tell
            end tell
            '''

        # Serialize launches so concurrent connections don't fight over the
        # "current window"
        with SSHManager._iterm_launch_lock:
            profiles_to_try = [iterm_profile]
            if iterm_profile != "Default":
                profiles_to_try.append("Default")

            for profile_attempt in profiles_to_try:
                try:
                    subprocess.run(['osascript', '-e', create_applescript(profile_attempt)],
                                   check=True, capture_output=True, text=True)

                    if profile_attempt != iterm_profile:
                        print(f"⚠️  Profile '{iterm_profile}' not found, using '{profile_attempt}' instead")

                    print(f"✅ Session launched successfully!")
                    return True

                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else str(e)
                    print(f"⚠️  Profile '{profile_attempt}' failed: {error_msg}")

            # Last resort: let iTerm2 pick the profile itself
            try:
                fallback_script = f'''
                tell application "iTerm"
                    activate
                    if (count of windows) = 0 then
                        set newWindow to (create window with default profile command "{escaped_command}")
                        set targetSession to current session of newWindow
                    else
                        tell current window
                            set newTab to (create tab with default profile command "{escaped_command}")
                            set targetSession to current session of newTab
                        end tell
                    end if
                    tell targetSession
                        set name to "{escaped_host_name}"
                    end tell
                end tell
                '''
                subprocess.run(['osascript', '-e', fallback_script],
                               check=True, capture_output=True, text=True)
                print(f"✅ Session launched successfully (using default profile)!")
                return True

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                print(f"✗ Error launching iTerm2 (all methods failed)")
                print(f"   Last error: {error_msg}")
                print(f"")
                print(f"💡 Troubleshooting tips:")
                print(f"   1. Make sure iTerm2 is installed and can be launched")
                print(f"   2. Check if iTerm2 has necessary permissions (System Settings > Privacy & Security)")
                print(f"   3. Try running iTerm2 manually first")
                print(f"   4. Check that you have a profile named 'Default' in iTerm2 preferences")

                # Nothing was launched, so nothing will clean up after us
                session.cleanup()
                return False

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
