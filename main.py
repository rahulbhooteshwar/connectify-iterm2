#!/usr/bin/env python3
"""
SSH Session Manager for iTerm2
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
import getpass
import time
from pathlib import Path
import inquirer
from inquirer.themes import GreenPassion
import shutil
import threading
import glob

# Custom theme for better visibility
class CustomTheme(GreenPassion):
    def __init__(self):
        super().__init__()
        # Enhanced visual indicators
        self.List.selection_cursor = "🔸"

class SSHManager:
    def __init__(self, config_file="~/.ssh_manager_config.json"):
        self.config_file = Path(config_file).expanduser()
        self.config = self.load_config()
        # Start background cleanup of old temp password files
        self.cleanup_old_temp_files()

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
                    "iterm_profile": "Production",
                    "tags": ["production", "web"]
                },
                {
                    "name": "Dev Server",
                    "hostname": "dev.example.com",
                    "username": "developer",
                    "port": 2222,
                    "auth_method": "key",
                    "ssh_key_path": "~/.ssh/dev_server_key",
                    "iterm_profile": "Development",
                    "tags": ["development", "testing"]
                }
            ]
        }

        os.makedirs(self.config_file.parent, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(sample_config, f, indent=2, ensure_ascii=False)

        print(f"Created sample configuration at {self.config_file}")
        print("Please edit this file to add your SSH hosts.")

    def store_password(self, service_name, username, password):
        """Store password in macOS Keychain using consolidated storage"""
        try:
            # Use a single service name for all SSH passwords
            ssh_service = "ssh-session-manager"

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
            ssh_service = "ssh-session-manager"
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
            # Search in name and tags only (excluding hostname)
            search_fields = [
                host.get('name', '').lower(),
                ' '.join(host.get('tags', [])).lower()
            ]

            if any(filter_term in field for field in search_fields):
                filtered_hosts.append(host)

        return filtered_hosts

    def filter_hosts_internal(self, hosts, filter_term):
        """Internal filtering method for menu search"""
        if not filter_term:
            return hosts

        filter_term = filter_term.lower()
        filtered_hosts = []

        for host in hosts:
            # Search in name and tags only (excluding hostname)
            search_fields = [
                host.get('name', '').lower(),
                ' '.join(host.get('tags', [])).lower()
            ]

            if any(filter_term in field for field in search_fields):
                filtered_hosts.append(host)

        return filtered_hosts

    def display_host_menu(self, hosts, has_active_filter=False):
        """Display interactive menu for host selection with tag-based visual grouping and search"""
        if not hosts:
            print("No hosts found matching your criteria.")
            return None

        # Get terminal height for better display info
        terminal_height = shutil.get_terminal_size().lines

        # Show helpful info about scrolling if we have many hosts
        if len(hosts) > 10:
            print(f"📋 Found {len(hosts)} hosts. Use ↑/↓ arrows to scroll through options.\n")

        # Add search functionality option
        search_option = "🔍 Search/Filter hosts..."
        all_hosts = hosts.copy()  # Keep reference to all hosts
        internal_filter_active = False  # Track if internal search filter is active

        while True:
            # Group hosts by tags
            tag_groups = {}
            untagged_hosts = []

            for host in hosts:
                host_tags = host.get('tags', [])
                if not host_tags:
                    untagged_hosts.append(host)
                else:
                    # Use the first tag as primary category for grouping
                    primary_tag = host_tags[0]
                    if primary_tag not in tag_groups:
                        tag_groups[primary_tag] = []
                    tag_groups[primary_tag].append(host)

            # Build choices with visual grouping
            choices = []

            # Add search option at the top
            choices.append((search_option, "search"))

            # Add clear filter option if there's an active filter (command-line or internal search)
            if has_active_filter or internal_filter_active:
                choices.append(("🗑️  Clear filter and show all hosts", "clear_filter"))

            # Add separator
            if hosts:
                choices.append(("──────────────────────", None))

            # Add tagged groups
            for tag in sorted(tag_groups.keys()):
                # Add visual header for this tag group (non-selectable)
                tag_header = f"── {tag.upper()} ──"
                choices.append((tag_header, None))

                # Add hosts in this group
                for host in tag_groups[tag]:
                    tags_str = f" [{', '.join(host.get('tags', []))}]" if host.get('tags') else ""
                    display_name = f"  {host['name']} ({host['username']}@{host['hostname']}:{host['port']}){tags_str}"
                    choices.append((display_name, host))

            # Add untagged hosts if any
            if untagged_hosts:
                if tag_groups:  # Only add separator if there are tagged groups above
                    choices.append(("── UNTAGGED ──", None))

                for host in untagged_hosts:
                    display_name = f"  {host['name']} ({host['username']}@{host['hostname']}:{host['port']})"
                    choices.append((display_name, host))

            # If no hosts after filtering, show message
            if not hosts:
                choices.append(("── No hosts match current filter ──", None))
                choices.append(("↩️  Clear filter and show all hosts", "clear_filter"))

            questions = [
                inquirer.List(
                    'host',
                    message="Select SSH host to connect (↑/↓ scroll, Enter select, Ctrl+C exit):",
                    choices=choices,
                    carousel=True
                )
            ]

            try:
                answers = inquirer.prompt(questions, theme=CustomTheme())
                if not answers:
                    return None

                selected = answers['host']

                if selected == "search":
                    # Handle search functionality
                    search_question = [
                        inquirer.Text(
                            'search_term',
                            message="Enter search term (name or tags):",
                            default=""
                        )
                    ]
                    search_answer = inquirer.prompt(search_question, theme=CustomTheme())

                    if search_answer and search_answer['search_term']:
                        # Filter hosts based on search term
                        hosts = self.filter_hosts_internal(all_hosts, search_answer['search_term'])
                        internal_filter_active = True  # Mark that internal filter is active
                        if not hosts:
                            print(f"No hosts found matching '{search_answer['search_term']}'")
                            input("Press Enter to continue...")
                    else:
                        # Empty search term, show all hosts
                        hosts = all_hosts
                        internal_filter_active = False
                    continue

                elif selected == "clear_filter":
                    # Reset to show all hosts and clear internal filter
                    hosts = all_hosts
                    internal_filter_active = False
                    continue

                elif selected is not None:  # Valid host selected
                    return selected
                # If None (header selected), continue the loop to ask again

            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return None

    def display_simple_host_menu(self, hosts):
        """Display simple numbered list for host selection"""
        if not hosts:
            print("No hosts found matching your criteria.")
            return None

        # Group hosts by tags for organized display
        tag_groups = {}
        untagged_hosts = []

        for host in hosts:
            host_tags = host.get('tags', [])
            if not host_tags:
                untagged_hosts.append(host)
            else:
                primary_tag = host_tags[0]
                if primary_tag not in tag_groups:
                    tag_groups[primary_tag] = []
                tag_groups[primary_tag].append(host)

        print(f"\n📋 Available SSH Hosts ({len(hosts)} total):")
        print("=" * 60)

        host_list = []
        index = 1

        # Display tagged groups
        for tag in sorted(tag_groups.keys()):
            print(f"\n── {tag.upper()} ──")
            for host in tag_groups[tag]:
                tags_str = f" [{', '.join(host.get('tags', []))}]" if host.get('tags') else ""
                print(f"{index:2}. {host['name']} ({host['username']}@{host['hostname']}:{host['port']}){tags_str}")
                host_list.append(host)
                index += 1

        # Display untagged hosts
        if untagged_hosts:
            if tag_groups:
                print(f"\n── UNTAGGED ──")
            for host in untagged_hosts:
                print(f"{index:2}. {host['name']} ({host['username']}@{host['hostname']}:{host['port']})")
                host_list.append(host)
                index += 1

        print("\nOptions:")
        print("  0. Exit")
        print("  s. Search/filter hosts")
        print("  c. Clear current filter (show all hosts)")

        while True:
            try:
                choice = input(f"\nSelect host (1-{len(host_list)}, 0=exit, s=search, c=clear filter): ").strip().lower()

                if choice == '0' or choice == 'exit' or choice == 'q':
                    return None
                elif choice == 's' or choice == 'search':
                    search_term = input("Enter search term (name or tags): ").strip()
                    if search_term:
                        filtered_hosts = self.filter_hosts_internal(hosts, search_term)
                        if filtered_hosts:
                            return self.display_simple_host_menu(filtered_hosts)
                        else:
                            print(f"No hosts found matching '{search_term}'")
                            continue
                    else:
                        continue
                elif choice == 'c' or choice == 'clear':
                    # Clear terminal and filter by returning to display all hosts
                    import os
                    os.system('clear')
                    print("🗑️  Filter cleared, showing all hosts...\n")
                    all_hosts = self.config.get('hosts', [])
                    return self.display_simple_host_menu(all_hosts)
                elif choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(host_list):
                        return host_list[choice_num - 1]
                    else:
                        print(f"Please enter a number between 1 and {len(host_list)}")
                else:
                    print("Invalid choice. Please enter a number, 's' for search, 'c' to clear filter, or '0' to exit.")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return None
            except ValueError:
                print("Invalid input. Please enter a number.")

    def build_ssh_command(self, host, password=None, temp_file=None):
        """Build SSH command for the selected host"""
        hostname = host['hostname']
        username = host['username']
        port = host.get('port', 22)
        auth_method = host.get('auth_method', 'password')

        # Try to use sshpass for password authentication if available
        if auth_method == 'password' and password and temp_file:
            # Check if sshpass is available
            try:
                subprocess.run(['which', 'sshpass'], check=True, capture_output=True)
                # Use temporary file approach to hide password completely
                ssh_cmd = f"sshpass -f {temp_file} ssh -o StrictHostKeyChecking=no -p {port} {username}@{hostname}"
                return ssh_cmd, True  # Return tuple indicating sshpass is used
            except subprocess.CalledProcessError:
                print("ℹ sshpass not found, falling back to manual password entry")

        # Standard SSH command
        ssh_cmd = f"ssh -p {port}"

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
                # print("📱 iTerm2 not running, launching it first...")

                # Launch iTerm2
                launch_script = '''
                tell application "iTerm"
                    activate
                end tell
                '''

                subprocess.run(['osascript', '-e', launch_script], check=True)

                # Wait a moment for iTerm2 to fully start
                time.sleep(2)
                # print("✅ iTerm2 launched successfully")

        except subprocess.CalledProcessError as e:
            # If AppleScript fails, try launching iTerm2 directly
            print("ℹ️  Attempting to launch iTerm2 directly...")
            try:
                subprocess.run(['open', '-a', 'iTerm'], check=True)
                time.sleep(2)
                print("✅ iTerm2 launched using 'open' command")
            except subprocess.CalledProcessError:
                print("⚠️  Warning: Could not verify or launch iTerm2. Proceeding anyway...")
        except Exception as e:
            print(f"⚠️  Warning: Error checking iTerm2 status: {e}. Proceeding anyway...")

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

            password = self.get_password(service_name, username)

            if not password:
                print(f"Please enter password for {username}@{host['hostname']}")
                password = getpass.getpass("Password (will be stored in keychain): ")
                if password:
                    self.store_password(service_name, username, password)
                    # Verify it was stored
                    test_password = self.get_password(service_name, username)
                    if not test_password:
                        print("⚠ Warning: Password storage may have failed")

        # Generate unique temporary file name for password with timestamp
        temp_pass_file = None
        if host.get('auth_method') == 'password' and password:
            import time
            timestamp = int(time.time())  # Unix timestamp
            temp_filename = f".ssh_pass_{timestamp}_{uuid.uuid4().hex[:8]}"
            temp_pass_file = Path.home() / temp_filename

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

        # AppleScript to launch iTerm2 with specific profile and title
        applescript = f'''
        tell application "iTerm"
            activate
            if (count of windows) = 0 then
                create window with profile "{iterm_profile}"
            else
                tell current window
                    create tab with profile "{iterm_profile}"
                end tell
            end if
            tell current session of current window
                set name to "{escaped_host_name}"
                write text "{ssh_command}"
            end tell
        end tell
        '''

        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            print(f"✅ Session launched successfully!")

            # Schedule background cleanup using separate subprocess
            if temp_file_created and temp_pass_file:
                # print(f"🕐 Password file will be cleaned up in 60 seconds (background)...")

                # Use subprocess to run cleanup independently
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

        except subprocess.CalledProcessError as e:
            print(f"✗ Error launching iTerm2: {e}")
            print(f"SSH command: {ssh_command}")

            # If launch failed, clean up immediately
            if temp_file_created and temp_pass_file and temp_pass_file.exists():
                try:
                    temp_pass_file.unlink()
                    print(f"🧹 Cleaned up temporary password file (launch failed)")
                except Exception as e:
                    print(f"⚠ Warning: Could not remove temporary file {temp_pass_file}: {e}")

    def add_host(self):
        """Interactive host addition"""
        print("\n=== Add New SSH Host ===")

        questions = [
            inquirer.Text('name', message="Host display name"),
            inquirer.Text('hostname', message="Hostname/IP address"),
            inquirer.Text('username', message="Username"),
            inquirer.Text('port', message="SSH port", default="22"),
            inquirer.List('auth_method',
                         message="Authentication method",
                         choices=['password', 'key']),
        ]

        answers = inquirer.prompt(questions, theme=CustomTheme())
        if not answers:
            return

        # Additional questions based on auth method
        if answers['auth_method'] == 'key':
            key_questions = [
                inquirer.Text('ssh_key_path',
                             message="Path to SSH private key",
                             default="~/.ssh/id_rsa")
            ]
            key_answers = inquirer.prompt(key_questions, theme=CustomTheme())
            answers.update(key_answers)

        # Optional fields
        optional_questions = [
            inquirer.Text('iterm_profile',
                         message="iTerm2 profile name (optional)",
                         default="Default"),
            inquirer.Text('tags',
                         message="Tags (comma-separated, optional)")
        ]

        optional_answers = inquirer.prompt(optional_questions, theme=CustomTheme())
        answers.update(optional_answers)

        # Process tags
        if answers.get('tags'):
            answers['tags'] = [tag.strip() for tag in answers['tags'].split(',')]
        else:
            answers['tags'] = []

        # Convert port to integer
        try:
            answers['port'] = int(answers['port'])
        except ValueError:
            answers['port'] = 22

        # Add to config
        self.config.setdefault('hosts', []).append(answers)

        # Save config
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        print(f"Host '{answers['name']}' added successfully!")

        # Store password if needed
        if answers['auth_method'] == 'password':
            store_pwd = input("Store password in keychain now? (y/N): ").lower() == 'y'
            if store_pwd:
                password = getpass.getpass("Enter password: ")
                if password:
                    service_name = f"ssh-{answers['hostname']}"
                    self.store_password(service_name, answers['username'], password)

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

    def list_hosts(self, filter_term=None):
        """List all hosts or filtered hosts"""
        hosts = self.filter_hosts(filter_term)

        if not hosts:
            print("No hosts found.")
            return

        print(f"\n=== SSH Hosts{' (filtered)' if filter_term else ''} ===")
        for i, host in enumerate(hosts, 1):
            tags_str = f" [{', '.join(host.get('tags', []))}]" if host.get('tags') else ""
            auth_info = f" ({host.get('auth_method', 'password')})"
            print(f"{i:2}. {host['name']} - {host['username']}@{host['hostname']}:{host['port']}{auth_info}{tags_str}")

def main():
    parser = argparse.ArgumentParser(description="SSH Session Manager for iTerm2",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="""
╔══════════════════════════════════════════════════════════════╗
║                SSH Session Manager for iTerm2                ║
║                     Comprehensive Help                      ║
╚══════════════════════════════════════════════════════════════╝

🚀 QUICK START:
  launch                    # Interactive host selection
  launch prod               # Filter hosts containing "prod"
  launch --add              # Add a new SSH host
  launch --list             # List all configured hosts
  launch --ui               # Launch web interface

📖 DETAILED USAGE:

BASIC COMMANDS:
  launch                    Start interactive host selection
  launch <filter>           Filter hosts by name or tags
  launch --add              Add a new SSH host interactively
  launch --list             List all hosts without connecting
  launch --list <filter>    List hosts matching filter
  launch --debug            Debug keychain functionality
  launch --config <path>    Use custom config file
  launch --simple           Use numbered list instead of scrolling menu
  launch --ui               Launch web interface
  launch --ui --port 8080   Launch web interface on custom port
  launch --ui --share       Launch web interface with shareable link
  launch --silent           Launch web interface silently in background (port 7890)

INTERACTIVE FEATURES:
  🔍 Search/Filter          Search and filter hosts by name or tags
  ↑/↓ Navigation           Navigate through host list
  Enter                     Connect to selected host
  Ctrl+C                    Exit application

🏷️  HOST ORGANIZATION:
  • Hosts are grouped by tags (first tag = primary group)
  • Use descriptive tags like: production, staging, web, database
  • Filter by any tag or host name
  • Tags help organize large numbers of hosts

🔐 AUTHENTICATION:
  • Password auth: Stored securely in consolidated macOS Keychain storage
  • SSH key auth: Specify path to private key
  • Automatic password prompting if not stored
  • Single keyring permission for all SSH hosts
  • Optional sshpass integration for seamless connections

🎨 iTerm2 PROFILES:
  • Assign custom iTerm2 profiles to hosts
  • Different colors, fonts, and settings per environment
  • Automatic session naming with host information

📁 CONFIGURATION:
  Config file: ~/.ssh_manager_config.json

  Host properties:
    name           Display name for the host
    hostname       Server hostname or IP address
    username       SSH username
    port           SSH port (default: 22)
    auth_method    "password" or "key"
    ssh_key_path   Path to private key (for key auth)
    iterm_profile  iTerm2 profile name
    tags           Array of tags for organization

💡 TIPS:
  • Use meaningful host names and tags for easy filtering
  • Set up iTerm2 profiles for different environments
  • Use consistent tagging (e.g., env:prod, type:web)
  • Store frequently used connection details
  • Use the search feature for quick access to specific hosts

🔧 TROUBLESHOOTING:
  • Config issues: Check ~/.ssh_manager_config.json syntax
  • Keychain issues: Run 'launch --debug' to check password storage
  • SSH key problems: Verify file paths and permissions
  • iTerm2 not opening: Check if iTerm2 is installed
  • First-time setup: You'll be prompted once for keyring access

Built with ❤️  by RB (Rahul Bhooteshwar)
        """)
    parser.add_argument('filter', nargs='?', help='Filter hosts by name, hostname, or tags')
    parser.add_argument('--add', action='store_true', help='Add a new SSH host')
    parser.add_argument('--list', action='store_true', help='List all hosts without launching')
    parser.add_argument('--debug', action='store_true', help='Debug keychain functionality')
    parser.add_argument('--config', help='Path to config file', default='~/.ssh_manager_config.json')
    parser.add_argument('--simple', action='store_true', help='Use simple numbered list instead of scrolling menu')
    parser.add_argument('--ui', action='store_true', help='Launch web interface')
    parser.add_argument('--port', type=int, default=7860, help='Port for web interface (default: 7860)')
    parser.add_argument('--share', action='store_true', help='Create shareable link for web interface')
    parser.add_argument('--silent', action='store_true', help='Launch web interface silently in background (fixed port 7890, no browser)')

    args = parser.parse_args()

    manager = SSHManager(args.config)

    if args.debug:
        manager.debug_keychain()
        return

    if args.add:
        manager.add_host()
        return

    if args.list:
        manager.list_hosts(args.filter)
        return

    if args.ui or args.silent:
        # Launch web interface
        try:
            from api_server import launch_api_server
            if args.silent:
                # Silent mode: fixed port, no browser, background
                print("🔇 Starting SSH Session Manager API Server in silent mode...")
                print("🌐 Server will run on http://localhost:7890")
                print("📋 Use Ctrl+C to stop the server")
                launch_api_server(args.config, 7890, "127.0.0.1", silent=True)
            else:
                # Normal UI mode
                print("🌐 Starting SSH Session Manager Web Interface...")
                print(f"🚀 Server will be available at http://localhost:{args.port}")
                if not args.share:
                    # Open browser automatically for local development
                    import webbrowser
                    import threading
                    def open_browser():
                        import time
                        time.sleep(1.5)  # Wait for server to start
                        webbrowser.open(f"http://localhost:{args.port}")
                    threading.Thread(target=open_browser, daemon=True).start()

                launch_api_server(args.config, args.port, "0.0.0.0" if args.share else "127.0.0.1", silent=False)
        except ImportError as e:
            print("❌ Web interface dependencies not installed.")
            print(f"Missing: {e}")
            print("Please run: uv sync")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error launching web interface: {e}")
            sys.exit(1)
        return

    # Main functionality: filter and launch
    initial_filter = args.filter

    while True:
        hosts = manager.filter_hosts(initial_filter)

        if not hosts:
            if initial_filter:
                print(f"No hosts found matching \"{initial_filter}\".")
            else:
                print("No hosts found.")
            return

        # Choose menu style based on user preference
        if args.simple:
            selected_host = manager.display_simple_host_menu(hosts)
        else:
            selected_host = manager.display_host_menu(hosts, has_active_filter=bool(initial_filter))

        if selected_host == "clear_filter":
            # This handles command-line filter clearing only
            # Internal filter clearing is handled within display_host_menu
            import os
            os.system('clear')
            print("🗑️  Filter cleared, showing all hosts...\n")
            initial_filter = None
            continue
        elif selected_host:
            manager.launch_iterm_session(selected_host)

            # Clear terminal and return to main menu
            import os
            os.system('clear')
            print("🔄 Returning to host selection...\n")

            # Clear the initial filter after first use to show all hosts
            initial_filter = None
        else:
            # User cancelled selection or pressed Ctrl+C
            print("👋 Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)