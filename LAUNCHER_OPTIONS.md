# 🚀 SSH Manager Launcher Options

Multiple ways to quickly launch your SSH Session Manager web interface:

## 📁 Available Files

| File | Purpose | Best For |
|------|---------|----------|
| `quick_launch.sh` | One-liner script | Terminal users, aliases |
| `shortcut_script.sh` | Simplified with error handling | macOS Shortcuts app |
| `launch_ui.sh` | Full-featured with logging | Direct execution, debugging |
| `SSH Manager Launcher.app` | Native macOS application | Dock, Applications folder |

## 🎯 Quick Comparison

### `quick_launch.sh` - Minimal
- **One line of code**
- **3-second wait** for server startup
- **No error handling**
- **Perfect for**: Terminal aliases, simple automation

### `shortcut_script.sh` - Balanced
- **15-second timeout** for server startup
- **Basic error handling**
- **Clean exit codes**
- **Perfect for**: macOS Shortcuts app

### `launch_ui.sh` - Full-Featured
- **30-second timeout** with progress messages
- **Detailed logging** and status updates
- **Comprehensive error handling**
- **Perfect for**: Direct execution, troubleshooting

### `SSH Manager Launcher.app` - Native
- **macOS notifications**
- **Error dialogs**
- **Can be added to Dock**
- **Perfect for**: Non-technical users, GUI preference

## ⚡ Quick Setup Examples

### For Shortcuts App
```bash
# Use this path in "Run Shell Script" action:
/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/shortcut_script.sh
```

### For Terminal Alias
```bash
# Add to your ~/.zshrc or ~/.bash_profile:
alias sshui="/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/quick_launch.sh"

# Then just type: sshui
```

### For Dock/Applications
```bash
# Copy the app to Applications:
cp -r "SSH Manager Launcher.app" /Applications/
```

### For Keyboard Shortcut
1. Create shortcut in Shortcuts app
2. Assign keyboard shortcut (e.g., `Cmd+Shift+S`)

## 🔧 Customization

All scripts can be customized by editing these variables:
```bash
PORT=7890                           # Change server port
URL="http://localhost:$PORT"        # Change URL
LAUNCH_PATH="/path/to/dist/launch"   # Change executable path
```

## 📋 Usage Patterns

### Development Workflow
```bash
./launch_ui.sh      # Start with logging for debugging
```

### Daily Use
```bash
./quick_launch.sh   # Fast startup for regular use
```

### Automation/Scripts
```bash
./shortcut_script.sh && echo "SSH Manager ready"
```

### GUI Users
Double-click `SSH Manager Launcher.app`

---

**Choose the option that best fits your workflow!** 🎉
