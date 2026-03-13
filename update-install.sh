#!/bin/bash

# Quick update script to install the newly built connectify

INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/connectify"

echo "🔄 Updating Connectify installation..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$LIB_DIR"

# Remove old installation
rm -rf "$LIB_DIR"

# Copy new files
mkdir -p "$LIB_DIR"
cp -R dist/connectify/* "$LIB_DIR/"

# Make executable
chmod +x "$LIB_DIR/connectify"

# Create or update symlink
rm -f "$INSTALL_DIR/connectify"
ln -s "$LIB_DIR/connectify" "$INSTALL_DIR/connectify"

echo "✅ Connectify updated successfully!"
echo ""
echo "Installed to: $INSTALL_DIR/connectify"
echo ""
echo "Test the fix:"
echo "  connectify ui stop"
echo "  connectify ui status"
echo ""

# Check PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "⚠️  Note: ~/.local/bin is not in your PATH"
    echo "   Add this to your ~/.zshrc or ~/.bashrc:"
    echo '   export PATH="$HOME/.local/bin:$PATH"'
    echo ""
fi
