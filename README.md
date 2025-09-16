# SSH Session Manager for iTerm2

A powerful command-line utility to manage and launch SSH sessions with credential storage and iTerm2 profile support on macOS.

## Features

- 🔐 **Secure credential storage** using macOS Keychain
- 🎯 **Interactive host selection** with tag-based filtering
- 🖥️ **iTerm2 integration** with custom profiles
- 🔍 **Smart search and filtering** by name or tags
- ⚡ **Fast host management** - add, list, and connect
- 🏷️ **Tag-based organization** for better host grouping
- 🌐 **Web interface** - Modern tile-based UI for easy host management

## Quick Installation

```bash
make install
```

This creates a standalone `launch` command that works without Python environments.

## Quick Start for Developers

```bash
# 1. Install uv (if not already installed)
brew install uv

# 2. Clone and setup
git clone <repository-url>
cd iterm2-ssh-session-manager

# 3. Set up environment and run
make setup
make dev       # Terminal interface
make ui        # Web interface
```

## Usage

### Terminal Interface
```bash
launch                    # Interactive host selection
launch production         # Filter hosts by "production"
launch --add              # Add a new SSH host
launch --list             # List all configured hosts
launch --debug            # Debug keychain issues
launch --simple           # Use numbered list instead of scrolling menu
```

### Web Interface
```bash
launch --ui               # Launch web interface on port 7860
launch --ui --port 8080   # Launch on custom port
launch --ui --share       # Create shareable link
launch --silent           # Launch silently in background (port 7890)
```

The web interface provides:
- 🎨 **Tile-based host display** organized by tags
- 🔍 **Real-time search** and filtering
- 🖱️ **Click-to-connect** functionality
- 📱 **Responsive design** for desktop and mobile
- 🎯 **Visual host information** with auth method indicators

### Auto-Start Web Interface on macOS Login

For seamless SSH management, you can configure the web interface to automatically start when you log into macOS.

#### Method 1: macOS Login Items (Recommended)

1. **First, install the application:**
   ```bash
   make install
   ```

2. **Open System Preferences:**
   - Go to **System Preferences** → **Users & Groups**
   - Click on your user account
   - Select the **Login Items** tab

3. **Add SSH Session Manager:**
   - Click the **"+"** button
   - Navigate to `/usr/local/bin/launch` (or use Spotlight to find "launch")
   - Select it and click **"Add"**

4. **Configure for silent startup:**
   - In the Login Items list, find "launch"
   - Double-click to edit the command
   - Change it to: `/usr/local/bin/launch --silent`
   - Check **"Hide"** to prevent terminal windows from appearing

5. **Test the setup:**
   - Log out and log back in
   - The web interface should be available at: **http://localhost:7890**
   - No browser window will open automatically

#### Method 2: launchd Service (Advanced)

For more control, create a launchd service:

1. **Create the plist file:**
   ```bash
   mkdir -p ~/Library/LaunchAgents
   cat > ~/Library/LaunchAgents/com.rb.ssh-session-manager.plist << 'EOF'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.rb.ssh-session-manager</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/local/bin/launch</string>
           <string>--silent</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/tmp/ssh-session-manager.log</string>
       <key>StandardErrorPath</key>
       <string>/tmp/ssh-session-manager.error.log</string>
   </dict>
   </plist>
   EOF
   ```

2. **Load the service:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.rb.ssh-session-manager.plist
   ```

3. **Verify it's running:**
   ```bash
   launchctl list | grep ssh-session-manager
   curl -s -I http://localhost:7890 | head -1
   ```

4. **To stop the service:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.rb.ssh-session-manager.plist
   ```

#### Benefits of Auto-Start

- 🚀 **Instant access** - SSH management always available at http://localhost:7890
- 🔇 **Silent operation** - No popups or browser windows on startup
- 🔒 **Secure** - Uses fixed port 7890, separate from manual UI sessions
- ⚡ **Fast** - Web interface loads instantly when needed
- 🎯 **Convenient** - Perfect for daily SSH workflow

## Configuration

On first run, a sample configuration is created at `~/.ssh_manager_config.json`:

```json
{
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
```

## Host Configuration Options

- **name**: Display name for the host
- **hostname**: Server hostname or IP address
- **username**: SSH username
- **port**: SSH port (default: 22)
- **auth_method**: `"password"` or `"key"`
- **ssh_key_path**: Path to private key (for key auth)
- **iterm_profile**: iTerm2 profile name (optional)
- **tags**: Array of tags for organization and filtering

## Prerequisites

### For End Users
- macOS
- iTerm2

### For Development/Building
- macOS
- iTerm2
- **uv** - Fast Python package manager and version manager

## Setting Up Development Environment

### 1. Install uv (if not already installed)

**Option A: Using Homebrew (Recommended)**
```bash
brew install uv
```

**Option B: Using curl**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Option C: Using pip**
```bash
pip install uv
```

### 2. Clone and Setup Project

```bash
# Clone the repository
git clone <repository-url>
cd iterm2-ssh-session-manager

# uv will automatically:
# - Install Python 3.12 (specified in .python-version)
# - Create virtual environment
# - Install all dependencies from pyproject.toml
# - Sync lockfile (uv.lock)

# Install dependencies
uv sync

# Activate virtual environment (optional - uv run handles this automatically)
source .venv/bin/activate
```

### 3. Verify Installation

```bash
# Run with uv (recommended - handles environment automatically)
uv run python main.py --help

# Or activate environment first, then run
source .venv/bin/activate
python main.py --help
```

## Development Workflow

```bash
# Set up development environment
make setup

# Run in development mode (terminal)
make dev

# Launch web interface
make ui

# Run with arguments in development
uv run python main.py --list
uv run python main.py --ui --port 8080
```

## Building from Source

```bash
# Build standalone executable
make build

# Build and install globally
make install

# Clean build artifacts
make clean
```

## Manual Development Commands

```bash
# Install/update dependencies
uv sync

# Add new dependency
uv add <package-name>

# Run the application (development)
uv run python main.py

# Run with arguments
uv run python main.py --list

# Install PyInstaller for building
uv add pyinstaller

# Build executable manually
uv run pyinstaller launch.spec

# Install globally
sudo cp ./dist/launch /usr/local/bin/launch
```

## Uninstalling

```bash
sudo rm /usr/local/bin/launch
```

## Security

- Passwords are stored securely in macOS Keychain
- SSH keys use standard SSH key authentication
- Temporary password files are created with secure permissions and automatically cleaned up

## 🚀 macOS Shortcuts Integration

Create convenient shortcuts to launch the SSH Manager web interface with a single click:

### Quick Setup
1. **Open Shortcuts app** on macOS
2. **Create new shortcut** → Add "Run Shell Script" action
3. **Paste this path**: `/path/to/your/ssh-manager/shortcut_script.sh`
4. **Name it** "SSH Manager" and optionally add to Dock

### What it does:
- ✅ Checks if server is running on port 7890
- 🚀 Launches server in silent mode if needed
- 🌐 Opens `http://localhost:7890` in your browser
- 📱 Works with Siri voice commands

### Detailed Setup Guide
See **[MACOS_SHORTCUT_SETUP.md](MACOS_SHORTCUT_SETUP.md)** for complete step-by-step instructions, troubleshooting, and advanced features.

## License

MIT License

---

Built with ❤️ by RB (Rahul Bhooteshwar)
