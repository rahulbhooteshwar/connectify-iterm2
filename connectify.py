#!/usr/bin/env python3
"""
Connectify - SSH Session Manager CLI Wrapper
Provides unified interface for SSH connections and UI server management
"""

import sys
import os
import subprocess
import argparse
import time
import signal

# Import version info
try:
    from version import VERSION, BUILD_DATE
except ImportError:
    VERSION = "unknown"
    BUILD_DATE = "unknown"

# Constants
UI_PORT = 7890
LOG_FILE = os.path.expanduser("~/.connectify/ui.log")
PID_FILE = os.path.expanduser("~/.connectify/ui.pid")


def ensure_connectify_dir():
    """Ensure ~/.connectify directory exists"""
    connectify_dir = os.path.expanduser("~/.connectify")
    os.makedirs(connectify_dir, exist_ok=True)
    return connectify_dir


def is_ui_running():
    """Check if UI server is running on port 7890"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{UI_PORT}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0 and result.stdout.strip()
    except Exception:
        return False


def get_ui_pid():
    """Get UI server PID from port"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{UI_PORT}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None


def start_ui():
    """Start UI server in background"""
    if is_ui_running():
        print(f"✅ Connectify UI server is already running on http://localhost:{UI_PORT}")
        return 0
    
    ensure_connectify_dir()
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine how to launch the UI server
    # Check if we're running from PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running from PyInstaller bundle
        # Get the path to the connectify executable
        connectify_exe = sys.executable
        launch_cmd = f"{connectify_exe} --silent"
    elif os.path.exists(os.path.join(script_dir, "main.py")):
        # Running from source - use uv run
        launch_cmd = f"cd {script_dir} && uv run python main.py --silent"
    else:
        print("❌ Error: Cannot determine how to launch UI server.")
        return 1
    
    print(f"🚀 Starting Connectify UI server on http://localhost:{UI_PORT}...")
    print("⏳ First run may take a moment to initialize...")
    
    # Start server in background, redirect output to log file
    # Open log file in append mode and keep it open by passing file descriptor
    log_fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    process = subprocess.Popen(
        launch_cmd,
        shell=True,
        stdout=log_fd,
        stderr=log_fd,
        start_new_session=True,  # Detach from parent
        close_fds=False  # Keep log file descriptor open
    )
    # Don't close log_fd here - let the subprocess inherit it
    
    # Wait for server to start with progressive retry
    # First run can take 5-10 seconds due to initialization
    max_wait = 12  # Total wait time in seconds
    check_interval = 1  # Check every second
    waited = 0
    
    while waited < max_wait:
        time.sleep(check_interval)
        waited += check_interval
        
        if is_ui_running():
            pid = get_ui_pid()
            if pid:
                # Save PID for future reference
                with open(PID_FILE, 'w') as f:
                    f.write(pid)
            print(f"✅ Connectify UI server started successfully!")
            print(f"🌐 Access it at: http://localhost:{UI_PORT}")
            print(f"📋 Logs: {LOG_FILE}")
            return 0
        
        # Show progress indicator for longer waits
        if waited >= 3 and waited % 2 == 0:
            print(f"   Still initializing... ({waited}s)")
    
    # If we get here, server didn't start in time
    print("❌ Failed to start UI server. Check logs for details:")
    print(f"   tail -f {LOG_FILE}")
    print()
    print("   The server may still be starting. Check status with:")
    print("   connectify ui status")
    return 1


def stop_ui():
    """Stop UI server"""
    if not is_ui_running():
        print("ℹ️  Connectify UI server is not running")
        return 0
    
    pid = get_ui_pid()
    if not pid:
        print("⚠️  Cannot determine UI server PID")
        return 1
    
    print(f"🛑 Stopping Connectify UI server (PID: {pid})...")
    
    try:
        # Kill all processes using port 7890
        # This is more reliable than trying to track PIDs
        result = subprocess.run(
            f"lsof -ti :{UI_PORT} | xargs kill -9",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        time.sleep(1)
        
        if not is_ui_running():
            print("✅ Connectify UI server stopped")
            # Clean up PID file
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            return 0
        else:
            print("❌ Failed to stop UI server")
            print("   Try manually: lsof -ti :7890 | xargs kill -9")
            return 1
    except subprocess.TimeoutExpired:
        print("❌ Timeout while stopping UI server")
        return 1
    except Exception as e:
        print(f"❌ Error stopping UI server: {e}")
        return 1


def restart_ui():
    """Restart UI server"""
    print("🔄 Restarting Connectify UI server...")
    stop_ui()
    time.sleep(1)
    return start_ui()


def show_logs():
    """Show UI server logs"""
    if not os.path.exists(LOG_FILE):
        print(f"ℹ️  No log file found at {LOG_FILE}")
        print("   The UI server may not have been started yet.")
        return 1
    
    print(f"📋 Connectify UI Server Logs ({LOG_FILE}):")
    print("=" * 60)
    
    try:
        with open(LOG_FILE, 'r') as f:
            print(f.read())
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return 1
    
    return 0


def ui_status():
    """Show UI server status"""
    # Show version info
    print(f"Connectify v{VERSION} ({BUILD_DATE})")
    print()
    
    # Check if server is running
    if is_ui_running():
        pid = get_ui_pid()
        print(f"✅ Connectify UI server is running")
        print(f"   PID: {pid}")
        print(f"   URL: http://localhost:{UI_PORT}")
        print(f"   Logs: {LOG_FILE}")
    else:
        print("❌ Connectify UI server is not running")
        print(f"   Start it with: connectify ui start")
    
    # Check auto-start configuration
    print()
    launchagent_plist = os.path.expanduser("~/Library/LaunchAgents/com.connectify.ui.plist")
    
    if os.path.exists(launchagent_plist):
        # Check if it's loaded
        result = subprocess.run(
            "launchctl list | grep com.connectify.ui",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("🔄 Auto-start: ✅ ENABLED")
            print("   The UI server will start automatically on login")
            print()
            print("   To disable auto-start:")
            print("   curl -fsSL https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/setup-autostart.sh | bash -s disable")
        else:
            print("🔄 Auto-start: ⚠️  CONFIGURED but not loaded")
            print("   LaunchAgent will activate on next login")
            print()
            print("   To load now:")
            print("   launchctl load ~/Library/LaunchAgents/com.connectify.ui.plist")
    else:
        print("🔄 Auto-start: ❌ DISABLED")
        print("   The UI server will not start automatically on login")
        print()
        print("   To enable auto-start:")
        print("   curl -fsSL https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/setup-autostart.sh | bash")
    
    return 0 if is_ui_running() else 1


def handle_profiles_command(command):
    """Handle 'connectify profiles ...' subcommands"""
    try:
        import iterm_profiles
    except ImportError:
        print("❌ Error: profile support not available. Installation may be corrupted.")
        return 1

    if command == 'install':
        result = iterm_profiles.install_bundled_profiles(force=True)
        iterm_profiles.warn_if_browser_plugin_missing()
        print()
        print("💡 Restart iTerm2 (or open a new window) if the profiles don't show up right away")
        return 1 if result['errors'] else 0
    elif command in ('list', 'status'):
        iterm_profiles.print_profiles_status()
        return 0
    else:
        print(f"❌ Unknown profiles command: {command}")
        print("   Usage: connectify profiles [install|list]")
        return 1


def describe_openssh():
    """Report whether ssh can take secrets from Connectify's askpass helper.

    Passwords and key passphrases are delivered via SSH_ASKPASS_REQUIRE=force,
    which OpenSSH gained in 8.4. Older versions just prompt in the terminal.
    """
    try:
        result = subprocess.run(['ssh', '-V'], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "❌ ssh not found"

    banner = (result.stderr or result.stdout).strip().split(',')[0]

    try:
        version = banner.split('_', 1)[1]
        major, minor = version.split('.')[:2]
        supported = (int(major), int(''.join(c for c in minor if c.isdigit()) or 0)) >= (8, 4)
    except (IndexError, ValueError):
        return f"{banner} (could not check askpass support)"

    if supported:
        return f"{banner} ✅ askpass supported (no sshpass needed)"
    return (f"{banner} ⚠️  older than 8.4 - passwords will be prompted in the "
            f"terminal instead of being supplied automatically")


def run_doctor():
    """Print everything useful for diagnosing a broken setup"""
    print(f"Connectify v{VERSION} ({BUILD_DATE})")
    print("=" * 60)

    # Where are we running from
    print("\n🔧 Installation")
    if getattr(sys, 'frozen', False):
        print(f"   Executable   : {sys.executable}")
    else:
        print(f"   Source       : {os.path.dirname(os.path.abspath(__file__))}")
    print(f"   Python       : {sys.version.split()[0]}")

    # UI server
    print("\n🌐 Web UI server")
    if is_ui_running():
        print(f"   Status       : ✅ running (PID {get_ui_pid()})")
        print(f"   URL          : http://localhost:{UI_PORT}")
    else:
        print("   Status       : ❌ not running ('connectify ui start')")
    print(f"   Log file     : {LOG_FILE}{'' if os.path.exists(LOG_FILE) else ' (none yet)'}")

    launchagent_plist = os.path.expanduser("~/Library/LaunchAgents/com.connectify.ui.plist")
    print(f"   Auto-start   : {'✅ configured' if os.path.exists(launchagent_plist) else '❌ disabled'}")

    # iTerm2 + profiles
    print("\n🎨 iTerm2")
    try:
        import iterm_profiles

        status = iterm_profiles.check_iterm2_requirements(quiet=True)
        print(f"   iTerm2       : {status['iterm2'] or '❌ not found - ' + iterm_profiles.ITERM_DOWNLOAD_URL}")
        print(f"   Plugin       : {status['browser_plugin'] or '⚠️  not found - ' + iterm_profiles.BROWSER_PLUGIN_DOWNLOAD_URL}")

        target_dir = iterm_profiles.dynamic_profiles_dir()
        for profile in iterm_profiles.list_bundled_profiles():
            installed = (target_dir / f"{profile['name']}.json").exists()
            print(f"   Profile      : {profile['name']} - {'✅ installed' if installed else '⬜ not installed'}")
    except Exception as e:
        print(f"   ⚠️  Could not inspect iTerm2: {e}")

    # Config + credentials
    print("\n📁 Configuration")
    try:
        from main import SSHManager, group_hosts

        manager = SSHManager()
        hosts = manager.config.get('hosts', [])
        groups, ungrouped = group_hosts(hosts)
        print(f"   Config file  : {manager.config_file}")
        print(f"   Hosts        : {len(hosts)} ({len(groups)} group(s), {len(ungrouped)} ungrouped)")

        without_credential = [h.get('name') for h in hosts if not h.get('credential')]
        if without_credential:
            print(f"   ⚠️  {len(without_credential)} host(s) have no credential: "
                  f"{', '.join(str(n) for n in without_credential[:5])}"
                  f"{'...' if len(without_credential) > 5 else ''}")

        print("\n🔐 Credentials vault")
        import vault as vault_module

        store = vault_module.Vault()
        if store.exists():
            print(f"   Vault file   : {store.path}")
            print("   Status       : ✅ present (locked - unlock it in the web UI)")
        else:
            print(f"   Vault file   : {store.path}")
            print("   Status       : ⬜ not created yet - open the Vault page in the web UI")

        print(f"   OpenSSH      : {describe_openssh()}")

        legacy = manager.legacy_keychain_passwords()
        if legacy:
            print(f"   Legacy keychain: {len(legacy)} password(s) still in the macOS Keychain")
            print("                    (they migrate into the vault when you create it)")
    except Exception as e:
        print(f"   ⚠️  Could not inspect configuration: {e}")
        return 1

    return 0


def handle_ui_command(args):
    """Handle UI subcommands"""
    if args.ui_command == 'start':
        return start_ui()
    elif args.ui_command == 'stop':
        return stop_ui()
    elif args.ui_command == 'restart':
        return restart_ui()
    elif args.ui_command == 'logs':
        return show_logs()
    elif args.ui_command == 'status':
        return ui_status()
    else:
        print(f"❌ Unknown UI command: {args.ui_command}")
        return 1


USAGE = """Connectify - SSH Session Manager for iTerm2

Connectify is managed from its web UI at http://localhost:{port}
This command exists to run that server and to diagnose problems.

  connectify ui start           Start the web UI server in the background
  connectify ui stop            Stop the server
  connectify ui restart         Restart the server
  connectify ui status          Show whether the server is running
  connectify ui logs            Print the server log

  connectify profiles list      Show bundled and available iTerm2 profiles
  connectify profiles install   (Re)install the bundled iTerm2 profiles

  connectify doctor             Full diagnostics (server, iTerm2, config, keychain)
  connectify version            Show version information
""".format(port=UI_PORT)


def main():
    """Main entry point for connectify CLI"""

    args = sys.argv[1:]
    command = args[0] if args else None

    # No arguments: show what this command can do
    if command is None or command in ('--help', '-h', 'help'):
        print(USAGE)
        sys.exit(0)

    if command in ('--version', '-v', 'version'):
        print(f"Connectify v{VERSION}")
        print(f"Build: {BUILD_DATE}")
        sys.exit(0)

    if command in ('doctor', 'diagnostics'):
        sys.exit(run_doctor())

    if command == 'profiles':
        parser = argparse.ArgumentParser(
            prog='connectify profiles',
            description='Manage the iTerm2 profiles shipped with Connectify'
        )
        parser.add_argument(
            'profiles_command',
            nargs='?',
            default='list',
            choices=['install', 'list', 'status'],
            help='Profile command (default: list)'
        )
        sys.exit(handle_profiles_command(parser.parse_args(args[1:]).profiles_command))

    if command == 'ui':
        parser = argparse.ArgumentParser(
            prog='connectify ui',
            description='Connectify web UI server management'
        )
        parser.add_argument(
            'ui_command',
            choices=['start', 'stop', 'restart', 'logs', 'status'],
            help='UI server command'
        )
        sys.exit(handle_ui_command(parser.parse_args(args[1:])))

    # Internal: 'connectify ui start' relaunches this executable with --silent to
    # run the server itself. --ui/--port/--config are the same entry point.
    if command in ('--silent', '--ui', '--port', '--config', '--share'):
        import main as ssh_main
        ssh_main.main()
        sys.exit(0)

    print(f"❌ Unknown command: {command}")
    print()
    print(USAGE)
    sys.exit(1)


if __name__ == "__main__":
    main()
