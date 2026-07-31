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
import keyring
import uuid
import time
from pathlib import Path
import threading
import glob

import iterm_profiles

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
                    "auth_method": "password",
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
                    "auth_method": "key",
                    "ssh_key_path": "~/.ssh/dev_server_key",
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

    def store_password(self, service_name, username, password):
        """Store password in macOS Keychain using consolidated storage"""
        try:
            # Use a single service name for all SSH passwords
            ssh_service = "connectify-iterm2"

            # Get existing passwords or create new storage
            existing_passwords = self.get_all_passwords()

            # Update the password for this host
            host_key = f"{username}@{service_name.replace('ssh-', '')}"
            existing_passwords[host_key] = password

            # Store the consolidated password data as JSON
            passwords_json = json.dumps(existing_passwords, ensure_ascii=False)
            keyring.set_password(ssh_service, "all_hosts", passwords_json)

            print(f"✓ Password stored securely")

            # Verify storage by trying to retrieve immediately
            retrieved_passwords = self.get_all_passwords()
            if host_key not in retrieved_passwords or retrieved_passwords[host_key] != password:
                print(f"⚠ Warning: Password verification failed")
        except Exception as e:
            print(f"✗ Error storing password: {e}")

    def get_password(self, service_name, username):
        """Retrieve password from consolidated keyring storage"""
        try:
            all_passwords = self.get_all_passwords()
            host_key = f"{username}@{service_name.replace('ssh-', '')}"
            return all_passwords.get(host_key)
        except Exception as e:
            print(f"✗ Error retrieving password: {e}")
            return None

    def get_all_passwords(self):
        """Retrieve all stored SSH passwords from keyring"""
        try:
            ssh_service = "connectify-iterm2"
            passwords_json = keyring.get_password(ssh_service, "all_hosts")

            if passwords_json:
                return json.loads(passwords_json)
            else:
                return {}
        except Exception as e:
            print(f"Error retrieving passwords: {e}")
            # Return empty dict if no passwords stored yet or error occurred
            return {}

    def cleanup_old_temp_files(self):
        """Clean up old temporary password files in background (non-blocking)"""
        def cleanup_worker():
            try:
                import time
                import os

                # Find all ssh temp password files in home directory
                home_dir = Path.home()
                pattern = str(home_dir / ".ssh_pass_*")
                temp_files = glob.glob(pattern)

                current_time = time.time()
                cleanup_threshold = 5 * 60  # 5 minutes in seconds
                cleaned_count = 0

                for temp_file_path in temp_files:
                    try:
                        temp_file = Path(temp_file_path)
                        filename = temp_file.name

                        # Extract timestamp from filename: .ssh_pass_TIMESTAMP_UUID
                        if filename.startswith('.ssh_pass_'):
                            parts = filename.split('_')
                            if len(parts) >= 3:  # ['.ssh', 'pass', 'timestamp', 'uuid']
                                try:
                                    file_timestamp = int(parts[2])
                                    file_age = current_time - file_timestamp

                                    # If file is older than 5 minutes, remove it
                                    if file_age > cleanup_threshold:
                                        temp_file.unlink()
                                        cleaned_count += 1
                                except (ValueError, IndexError):
                                    # If we can't parse timestamp, check file modification time as fallback
                                    file_mtime = temp_file.stat().st_mtime
                                    file_age = current_time - file_mtime
                                    if file_age > cleanup_threshold:
                                        temp_file.unlink()
                                        cleaned_count += 1
                    except (OSError, FileNotFoundError):
                        # File might have been deleted by another process, ignore
                        pass

                # Only print if we actually cleaned something (for debugging)
                if cleaned_count > 0:
                    print(f"🧹 Cleaned up {cleaned_count} old temporary password file(s)")

            except Exception as e:
                # Silently handle any errors in background cleanup
                pass

        # Run cleanup in background thread
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

    def build_ssh_command(self, host, password=None, temp_file=None):
        """Build SSH command for the selected host"""
        hostname = host['hostname']
        username = host['username']
        port = host.get('port', 22)
        auth_method = host.get('auth_method', 'password')

        # SSH keep-alive options disabled - no automatic disconnection
        keepalive_opts = ""

        # SSH "-o" options are configured per host from the UI. Fall back to
        # auth-method defaults for hosts that don't define them explicitly.
        auth_opts = " ".join(f"-o {opt}" for opt in resolve_ssh_options(host))

        # Try to use sshpass for password authentication if available
        if auth_method == 'password' and password and temp_file:
            # Check if sshpass is available - try common paths
            sshpass_path = None
            try:
                result = subprocess.run(['which', 'sshpass'], check=True, capture_output=True, text=True)
                sshpass_path = result.stdout.strip()
                if self.debug:
                    print(f"DEBUG: sshpass found at: {sshpass_path}")
            except subprocess.CalledProcessError:
                # Try common installation paths
                for path in ['/opt/homebrew/bin/sshpass', '/usr/local/bin/sshpass', '/usr/bin/sshpass']:
                    if Path(path).exists():
                        sshpass_path = path
                        if self.debug:
                            print(f"DEBUG: sshpass found at fallback path: {sshpass_path}")
                        break
            
            if sshpass_path:
                if self.debug:
                    print(f"DEBUG: Using temp file: {temp_file}")
                # Use temporary file approach to hide password completely
                ssh_cmd = f"{sshpass_path} -f {temp_file} ssh -o StrictHostKeyChecking=no {keepalive_opts} {auth_opts} -p {port} {username}@{hostname}"
                return ssh_cmd, True  # Return tuple indicating sshpass is used
            else:
                if self.debug:
                    print(f"DEBUG: sshpass not found in any location")
                print("ℹ sshpass not found, falling back to manual password entry")

        # Standard SSH command
        ssh_cmd = f"ssh -p {port} {keepalive_opts} {auth_opts}"

        if auth_method == 'key':
            ssh_key_path = host.get('ssh_key_path')
            if ssh_key_path:
                key_path = Path(ssh_key_path).expanduser()
                if key_path.exists():
                    ssh_cmd += f" -i {key_path}"
                else:
                    print(f"Warning: SSH key not found at {key_path}")

        ssh_cmd += f" {username}@{hostname}"
        return ssh_cmd, False  # Return tuple indicating sshpass is not used

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

    def launch_iterm_session(self, host):
        """Launch iTerm2 session with the specified host"""
        iterm_profile = host.get('iterm_profile', 'Default')

        # Show launching message
        host_name = host.get('name', f"{host['username']}@{host['hostname']}")
        print(f"🚀 Launching {host_name} session...")

        # Check if iTerm2 is running and launch it if not
        self._ensure_iterm_running()

        # Handle password authentication
        password = None
        if host.get('auth_method') == 'password':
            service_name = f"ssh-{host['hostname']}"
            username = host['username']
            
            if self.debug:
                print(f"DEBUG: Retrieving password for service_name={service_name}, username={username}")

            password = self.get_password(service_name, username)
            
            if self.debug:
                print(f"DEBUG: Retrieved password: {'[PRESENT]' if password else '[NOT FOUND]'}")

            if not password:
                # Sessions are always launched from the web UI, which checks for
                # a stored password before getting here - there is nobody to
                # prompt at this point.
                print(f"⚠️  Password required for {username}@{host['hostname']}")
                print(f"⚠️  Set it in the web UI (edit the host) and try again")
                raise ValueError(f"Password required for {host_name} but not stored in keychain")

        # Generate unique temporary file name for password with timestamp
        temp_pass_file = None
        if host.get('auth_method') == 'password' and password:
            import time
            timestamp = int(time.time())  # Unix timestamp
            temp_filename = f".ssh_pass_{timestamp}_{uuid.uuid4().hex[:8]}"
            temp_pass_file = Path.home() / temp_filename
            if self.debug:
                print(f"DEBUG: Will create temp password file: {temp_pass_file}")
        
        if self.debug:
            print(f"DEBUG: password is None: {password is None}")
            print(f"DEBUG: password bool: {bool(password)}")
            print(f"DEBUG: temp_pass_file: {temp_pass_file}")

        # Build SSH command
        ssh_command, uses_sshpass = self.build_ssh_command(host, password, temp_pass_file)

        # Handle secure password file for sshpass with proper cleanup
        temp_file_created = False
        if uses_sshpass and password and temp_pass_file:
            try:
                with open(temp_pass_file, 'w') as f:
                    f.write(password)
                os.chmod(temp_pass_file, 0o600)  # Secure permissions
                temp_file_created = True
            except Exception as e:
                print(f"Error creating temporary password file: {e}")
                return



        # Escape quotes and backslashes for AppleScript
        escaped_host_name = host_name.replace('\\', '\\\\').replace('"', '\\"')

        def create_applescript(profile_name):
            """Generate AppleScript with specified profile.
            
            Uses explicit tab/session references to prevent race conditions when
            multiple connections are launched simultaneously. The newTab/newWindow
            reference is captured immediately after creation and used for all
            subsequent operations, ensuring commands go to the correct tab even
            if the user switches tabs or other launches occur concurrently.
            """
            return f'''
            tell application "iTerm"
                activate
                if (count of windows) = 0 then
                    set newWindow to (create window with profile "{profile_name}")
                    set targetSession to current session of newWindow
                else
                    tell current window
                        set newTab to (create tab with profile "{profile_name}")
                        set targetSession to current session of newTab
                    end tell
                end if
                tell targetSession
                    set name to "{escaped_host_name}"
                    write text "{ssh_command}"
                end tell
            end tell
            '''

        # Acquire lock to serialize iTerm2 launches and prevent race conditions
        # when multiple connections are launched simultaneously from the UI
        with SSHManager._iterm_launch_lock:
            # Try launching with specified profile, fallback to Default if it fails
            launch_success = False
            profiles_to_try = [iterm_profile] if iterm_profile != "Default" else ["Default"]
            if iterm_profile != "Default":
                profiles_to_try.append("Default")  # Add Default as fallback

            last_error = None
            for profile_attempt in profiles_to_try:
                try:
                    applescript = create_applescript(profile_attempt)
                    result = subprocess.run(['osascript', '-e', applescript], check=True, capture_output=True, text=True)

                    if profile_attempt != iterm_profile:
                        print(f"⚠️  Profile '{iterm_profile}' not found, using '{profile_attempt}' instead")

                    print(f"✅ Session launched successfully!")
                    launch_success = True

                    # Schedule background cleanup using separate subprocess
                    if temp_file_created and temp_pass_file:
                        cleanup_command = [
                            'python3', '-c',
                            f'import time, os; time.sleep(60); '
                            f'os.remove("{temp_pass_file}") if os.path.exists("{temp_pass_file}") else None'
                        ]

                        # Start cleanup process in background and detach it
                        subprocess.Popen(
                            cleanup_command,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True  # Detach from parent process
                        )

                    break  # Success, exit the retry loop

                except subprocess.CalledProcessError as e:
                    last_error = e
                    error_msg = e.stderr if e.stderr else str(e)
                    print(f"⚠️  Profile '{profile_attempt}' failed: {error_msg}")
                    # Continue to next profile attempt

            # If all profile attempts failed, try without specifying a profile (last resort)
            if not launch_success:
                print("ℹ️  Trying to launch without profile specification...")
                try:
                    # Simple AppleScript without profile - uses explicit tab references
                    # to prevent race conditions (same pattern as create_applescript)
                    simple_script = f'''
                    tell application "iTerm"
                        activate
                        if (count of windows) = 0 then
                            set newWindow to (create window with default profile)
                            set targetSession to current session of newWindow
                        else
                            tell current window
                                set newTab to (create tab with default profile)
                                set targetSession to current session of newTab
                            end tell
                        end if
                        tell targetSession
                            set name to "{escaped_host_name}"
                            write text "{ssh_command}"
                        end tell
                    end tell
                    '''

                    result = subprocess.run(['osascript', '-e', simple_script], check=True, capture_output=True, text=True)
                    print(f"✅ Session launched successfully (using default profile)!")
                    launch_success = True

                    # Schedule background cleanup
                    if temp_file_created and temp_pass_file:
                        cleanup_command = [
                            'python3', '-c',
                            f'import time, os; time.sleep(60); '
                            f'os.remove("{temp_pass_file}") if os.path.exists("{temp_pass_file}") else None'
                        ]
                        subprocess.Popen(
                            cleanup_command,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True
                        )

                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else str(e)
                    print(f"✗ Error launching iTerm2 (all methods failed)")
                    print(f"   Last error: {error_msg}")
                    print(f"   SSH command: {ssh_command}")
                    print(f"")
                    print(f"💡 Troubleshooting tips:")
                    print(f"   1. Make sure iTerm2 is installed and can be launched")
                    print(f"   2. Check if iTerm2 has necessary permissions (System Preferences > Security & Privacy)")
                    print(f"   3. Try running iTerm2 manually first")
                    print(f"   4. Check if you have any profile named 'Default' in iTerm2 preferences")

                    # Clean up temp file
                    if temp_file_created and temp_pass_file and temp_pass_file.exists():
                        try:
                            temp_pass_file.unlink()
                            print(f"🧹 Cleaned up temporary password file (launch failed)")
                        except Exception as cleanup_error:
                            print(f"⚠ Warning: Could not remove temporary file {temp_pass_file}: {cleanup_error}")

    def debug_keychain(self):
        """Debug keychain storage and retrieval"""
        print("\n=== Keychain Debug Information ===")

        # Show keyring backend
        print(f"Keyring backend: {keyring.get_keyring()}")

        # Test basic functionality
        test_service = "ssh-manager-test"
        test_user = "testuser"
        test_password = "testpass123"

        print(f"\nTesting keychain with service '{test_service}' and user '{test_user}'...")

        # Store test password
        try:
            keyring.set_password(test_service, test_user, test_password)
            print("✓ Test password stored")
        except Exception as e:
            print(f"✗ Failed to store test password: {e}")
            return

        # Retrieve test password
        try:
            retrieved = keyring.get_password(test_service, test_user)
            if retrieved == test_password:
                print("✓ Test password retrieved successfully")
            else:
                print(f"✗ Test password mismatch. Expected: {test_password}, Got: {retrieved}")
        except Exception as e:
            print(f"✗ Failed to retrieve test password: {e}")

        # Clean up test
        try:
            keyring.delete_password(test_service, test_user)
            print("✓ Test password cleaned up")
        except Exception as e:
            print(f"⚠ Failed to clean up test password: {e}")

        # Show stored SSH passwords
        print(f"\nConsolidated Password Storage Status:")
        all_passwords = self.get_all_passwords()

        if all_passwords:
            print(f"✓ Found {len(all_passwords)} passwords in consolidated storage:")
            for host_key in all_passwords.keys():
                print(f"  - {host_key}")
        else:
            print(f"ℹ No passwords stored yet")

        # Verify each configured host can access its password
        print(f"\nHost Password Access Check:")
        hosts = self.config.get('hosts', [])
        password_hosts = [h for h in hosts if h.get('auth_method') == 'password']

        if password_hosts:
            for host in password_hosts:
                service_name = f"ssh-{host['hostname']}"
                username = host['username']
                try:
                    stored_pwd = self.get_password(service_name, username)
                    if stored_pwd:
                        print(f"✓ {username}@{host['hostname']} - password accessible")
                    else:
                        print(f"ℹ {username}@{host['hostname']} - no password stored")
                except Exception as e:
                    print(f"✗ {username}@{host['hostname']} - error: {e}")
        else:
            print("  No hosts configured for password authentication")

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
