# Connectify - SSH Session Manager for iTerm2

A powerful command-line utility to manage and launch SSH sessions with credential storage and iTerm2 profile support on macOS.

## Features

- 🔐 **Secure credential storage** using macOS Keychain
- 🎯 **Interactive host selection** with tag-based filtering
- 🖥️ **iTerm2 integration** with custom profiles
- 🔍 **Smart search and filtering** by name or tags
- ⚡ **Fast host management** - add, list, and connect
- 🏷️ **Tag-based organization** for better host grouping
- 🌐 **Web interface** - Modern tile-based UI for easy host management
- 🚀 **Background UI server** - Always-on web interface

## Quick Installation

### One-Line Install (Recommended)

No build required! Downloads pre-built binary:

```bash
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/install.sh | sh
```

This will:
- ✅ Download the latest pre-built binary
- ✅ Install to `~/.local/bin/connectify` (no sudo required!)
- ✅ Optionally setup auto-start
- ✅ Setup PATH if needed
- ✅ No Python or build tools required!

## Usage

### SSH Connection Management

```bash
connectify                    # Interactive host selection
connectify production         # Filter hosts by "production"
connectify --add              # Add a new SSH host
connectify --list             # List all configured hosts
connectify --help             # Show all options
```

### Background UI Server

The background UI server provides a web interface for managing SSH connections:

```bash
connectify ui start           # Start background UI server
connectify ui stop            # Stop UI server
connectify ui restart         # Restart UI server
connectify ui logs            # Show UI server logs
connectify ui status          # Check if UI server is running
```

Once started, access the UI at: **http://localhost:7890**

The web interface provides:
- 🎨 **Tile-based host display** organized by tags
- 🔍 **Real-time search** and filtering
- 🖱️ **Click-to-connect** functionality
- 📱 **Responsive design** for desktop and mobile

## Configuration

Configuration is stored at `~/.connectify/hosts.json`. On first run, a sample configuration is created automatically:

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

### Host Configuration Options

| Option | Description | Required |
|--------|-------------|----------|
| `name` | Display name for the host | Yes |
| `hostname` | Server hostname or IP address | Yes |
| `username` | SSH username | Yes |
| `port` | SSH port (default: 22) | No |
| `auth_method` | `"password"` or `"key"` | Yes |
| `ssh_key_path` | Path to private key (for key auth) | If using key auth |
| `iterm_profile` | iTerm2 profile name | No |
| `tags` | Array of tags for organization | No |

## Auto-Start on Login

The installer will offer to configure the UI server to start automatically when you log in. If you skipped this during installation, you can set it up anytime:

```bash
# Download and run the setup script
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/setup-autostart.sh | bash -s enable

# Or if you have the repo cloned:
./setup-autostart.sh enable

# Check status
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/setup-autostart.sh | bash -s status

# Disable auto-start
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/setup-autostart.sh | bash -s disable
```

The auto-start feature creates a LaunchAgent that:
- Starts the UI server automatically on login
- Keeps the server running in the background
- Restarts the server if it crashes
- Logs output to `/tmp/connectify-autostart.log`

## Uninstallation

### One-Line Uninstall

```bash
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/uninstall.sh | sh
```

### Manual Uninstall

```bash
./uninstall.sh
```

The uninstaller will:
- Stop any running UI server
- Remove installed files
- Optionally remove configuration files
- Guide you through keychain cleanup

## Advanced Usage

### Custom Port for Temporary UI

```bash
connectify --ui               # Launch on port 7860
connectify --ui --port 8080   # Launch on custom port
connectify --ui --share       # Create shareable link (0.0.0.0)
```

### Debugging

```bash
connectify --debug            # Debug keychain functionality
connectify ui logs            # View UI server logs
```

### Simple Menu Mode

```bash
connectify --simple           # Use numbered list instead of scrolling menu
```

## Troubleshooting

### Command not found

Make sure `~/.local/bin` is in your PATH:

```bash
echo $PATH | grep ".local/bin"
```

If not, add it to your shell profile:

```bash
# For zsh (default on macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Note**: The installer will offer to do this automatically for you!

### UI server won't start

Check the logs:

```bash
connectify ui logs
```

Make sure port 7890 is not in use:

```bash
lsof -i :7890
```

### Keychain access issues

Run the debug command:

```bash
connectify --debug
```

### iTerm2 not opening

Verify iTerm2 is installed and set as default terminal.

## Security

- Passwords are stored securely in macOS Keychain
- SSH keys use standard SSH key authentication
- Temporary password files are created with secure permissions and automatically cleaned up
- UI server runs locally on 127.0.0.1 (not exposed to network by default)

## Requirements

- macOS (Apple Silicon or Intel)
- iTerm2

That's it! No Python or build tools needed for installation.

## Documentation

- **User Guide**: This file
- **Development Guide**: [DEVELOPMENT.md](DEVELOPMENT.md) - For developers who want to contribute

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## License

MIT License

## Support

- **Repository**: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager
- **Issues**: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager/issues
- **Discussions**: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager/discussions

---

Built with ❤️ by RB (Rahul Bhooteshwar)
