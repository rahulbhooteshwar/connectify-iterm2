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
    with open(LOG_FILE, 'w') as log:
        process = subprocess.Popen(
            launch_cmd,
            shell=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from parent
        )
    
    # Wait a moment and check if it started
    time.sleep(2)
    
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
    else:
        print("❌ Failed to start UI server. Check logs for details:")
        print(f"   tail -f {LOG_FILE}")
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
    if is_ui_running():
        pid = get_ui_pid()
        print(f"✅ Connectify UI server is running")
        print(f"   PID: {pid}")
        print(f"   URL: http://localhost:{UI_PORT}")
        print(f"   Logs: {LOG_FILE}")
        return 0
    else:
        print("❌ Connectify UI server is not running")
        print(f"   Start it with: connectify ui start")
        return 1


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


def main():
    """Main entry point for connectify CLI"""
    
    # Check if 'ui' command is being used
    if len(sys.argv) > 1 and sys.argv[1] == 'ui':
        # Create UI subcommand parser
        parser = argparse.ArgumentParser(
            prog='connectify ui',
            description='Connectify UI Server Management'
        )
        parser.add_argument(
            'ui_command',
            choices=['start', 'stop', 'restart', 'logs', 'status'],
            help='UI server command'
        )
        
        # Parse only the ui subcommand args
        args = parser.parse_args(sys.argv[2:])
        args.ui_command = sys.argv[2] if len(sys.argv) > 2 else None
        
        if not args.ui_command:
            parser.print_help()
            sys.exit(1)
        
        sys.exit(handle_ui_command(args))
    
    # Otherwise, delegate to main SSH functionality
    # Import main module and call it directly (works with PyInstaller)
    try:
        # When bundled by PyInstaller, we can import main directly
        import main as ssh_main
        ssh_main.main()
    except ImportError:
        # Fallback for development mode
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_py = os.path.join(script_dir, "main.py")
        
        if not os.path.exists(main_py):
            print("❌ Error: Cannot find main.py. Installation may be corrupted.")
            sys.exit(1)
        
        # Running from source - use uv run
        cmd = ["uv", "run", "python", main_py] + sys.argv[1:]
        
        try:
            result = subprocess.run(cmd, cwd=script_dir)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
