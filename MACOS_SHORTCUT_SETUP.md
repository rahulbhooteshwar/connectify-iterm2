# macOS Shortcut Setup Guide for SSH Session Manager

This guide will help you create a convenient macOS shortcut to launch your SSH Session Manager web interface with a single click.

## 📋 Prerequisites

- SSH Session Manager already built (`dist/launch` executable exists)
- macOS Monterey (12.0) or later
- Basic familiarity with macOS Shortcuts app

## 🎯 What This Does

The shortcut will:
1. **Check** if the SSH Manager server is already running on port 7890
2. **Launch** the server in silent mode if it's not running
3. **Open** `http://localhost:7890` in your default browser
4. **Show** notifications for success/failure

## 🚀 Method 1: Using macOS Shortcuts App (Recommended)

### Step 1: Open Shortcuts App
1. Press `Cmd + Space` and type "Shortcuts"
2. Click on the **Shortcuts** app to open it

### Step 2: Create New Shortcut
1. Click the **"+"** button in the top-right corner
2. Click **"Add Action"**

### Step 3: Add Shell Script Action
1. In the search bar, type **"Run Shell Script"**
2. Click on **"Run Shell Script"** action to add it

### Step 4: Configure the Script
1. In the script box, paste this command:
   ```bash
   /Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/shortcut_script.sh
   ```
2. Make sure **"Pass Input"** is set to **"to stdin"**
3. Leave **"Input"** as **"Shortcut Input"**

### Step 5: Name Your Shortcut
1. Click on **"Shortcut Name"** at the top
2. Type: **"SSH Manager"** (or your preferred name)

### Step 6: Add to Dock/Menu Bar (Optional)
1. Click the **"⚙️ Settings"** icon
2. Enable **"Add to Dock"**
3. Enable **"Add to Menu Bar"**
4. Choose an icon if desired

### Step 7: Test Your Shortcut
1. Click the **"▶️ Play"** button to test
2. Your browser should open to `http://localhost:7890`

## 🔧 Method 2: Using the Pre-built App

### Option A: Use the Generated App
1. Navigate to your SSH Manager directory
2. Double-click **"SSH Manager Launcher.app"**
3. The app will handle everything automatically

### Option B: Add App to Applications
1. Copy **"SSH Manager Launcher.app"** to `/Applications/`
2. Now you can launch it from Launchpad or Spotlight

## ⌨️ Method 3: Keyboard Shortcut

### Add Keyboard Shortcut to Your Shortcut
1. Open your shortcut in Shortcuts app
2. Click **"⚙️ Settings"**
3. Click **"Add Keyboard Shortcut"**
4. Press your desired key combination (e.g., `Cmd + Shift + S`)
5. Now you can launch with the keyboard shortcut

## 🛠️ Troubleshooting

### Permission Issues
If you get permission errors:
```bash
chmod +x /Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/shortcut_script.sh
```

### Script Not Found
Make sure the path in the shortcut matches your actual installation:
```bash
# Check if file exists
ls -la /Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/shortcut_script.sh

# If in different location, update the path in your shortcut
```

### Server Won't Start
1. Check if you can run manually:
   ```bash
   cd /Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager
   ./dist/launch --silent
   ```
2. Check for port conflicts:
   ```bash
   lsof -i :7890
   ```

### Browser Doesn't Open
- Check your default browser settings
- Try manually opening `http://localhost:7890`
- Restart the shortcut

## 📱 Advanced: iOS/iPadOS Integration

### Share Across Devices
1. In Shortcuts app, select your shortcut
2. Click **"Share"** icon
3. Choose **"Add to iCloud"**
4. Now available on iPhone/iPad (requires Mac to be on same network)

### Siri Integration
1. In shortcut settings, click **"Add to Siri"**
2. Record phrase: "Launch SSH Manager"
3. Now you can use voice commands

## 🎨 Customization Options

### Custom Icon
1. Edit shortcut → Settings → Icon
2. Choose from system icons or add custom image

### Custom Notifications
Edit the AppleScript version to customize notification messages:
```applescript
display notification "Your custom message" with title "SSH Manager"
```

### Different Port
If using a different port, edit the script files:
```bash
# Edit this line in shortcut_script.sh
PORT=7890  # Change to your port
```

## 📁 File Locations

After setup, you'll have these files:
```
/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/
├── launch_ui.sh                    # Detailed script with logging
├── shortcut_script.sh             # Simplified script for Shortcuts
├── SSH_Manager_Launcher.applescript # AppleScript source
├── SSH Manager Launcher.app       # macOS application
└── MACOS_SHORTCUT_SETUP.md       # This guide
```

## 🔄 Updating

When you rebuild your SSH Manager:
```bash
make build
```

The shortcuts will automatically use the new executable - no changes needed!

## ❓ FAQ

**Q: Can I change the port?**
A: Yes, edit `PORT=7890` in the script files to your desired port.

**Q: Will this work if I move the SSH Manager folder?**
A: No, you'll need to update the paths in your shortcuts.

**Q: Can I have multiple shortcuts for different configurations?**
A: Yes, create copies of the script with different parameters.

**Q: Does this work with VPNs?**
A: Yes, as long as localhost/127.0.0.1 is accessible.

## 🆘 Getting Help

If you encounter issues:
1. Check the console logs in Console.app
2. Run the script manually in Terminal for debugging
3. Verify file permissions and paths
4. Ensure SSH Manager builds successfully

---

**🎉 Enjoy your one-click SSH Manager access!**
