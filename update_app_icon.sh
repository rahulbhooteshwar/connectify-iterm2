#!/bin/bash

# Script to update the SSH Manager Launcher app icon

ICON_FILE="ssh.png"
APP_NAME="SSH Manager Launcher.app"
ICON_NAME="applet.icns"

echo "🎨 Updating SSH Manager Launcher icon..."

# Check if icon file exists
if [ ! -f "$ICON_FILE" ]; then
    echo "❌ Error: $ICON_FILE not found!"
    exit 1
fi

# Convert PNG to ICNS
echo "🔄 Converting PNG to ICNS format..."
sips -s format icns "$ICON_FILE" --out "ssh.icns"

# Create app bundle structure if needed
mkdir -p "$APP_NAME/Contents/Resources"

# Copy icon to app bundle
echo "📋 Copying icon to app bundle..."
cp "ssh.icns" "$APP_NAME/Contents/Resources/$ICON_NAME"

# Update Applications folder
echo "📱 Updating app in Applications..."
rm -rf "/Applications/$APP_NAME"
cp -r "$APP_NAME" /Applications/

# Refresh caches
echo "🔄 Refreshing Finder and Dock..."
touch "/Applications/$APP_NAME"
killall Finder 2>/dev/null
killall Dock 2>/dev/null

echo "✅ Icon updated successfully!"
echo "🚀 Check your dock - the SSH Manager should now show the new icon!"
