#!/bin/bash
set -e

# Connectify Installer - Downloads and installs pre-built binary
# No build required on user's machine!

VERSION="${CONNECTIFY_VERSION:-latest}"
GITHUB_REPO="rahulbhooteshwar/iterm2-ssh-session-manager"
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/connectify"
TEMP_DIR="/tmp/connectify-install-$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    printf "${BLUE}ℹ️  %s${NC}\n" "$1"
}

print_success() {
    printf "${GREEN}✅ %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}❌ %s${NC}\n" "$1"
}

print_warning() {
    printf "${YELLOW}⚠️  %s${NC}\n" "$1"
}

check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This installer is only for macOS"
        exit 1
    fi
}

check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "Please do not run this installer as root or with sudo"
        print_info "Connectify installs to your home directory and doesn't need sudo"
        exit 1
    fi
}

check_path() {
    # Check if ~/.local/bin is in PATH and guide user if not
    if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
        return 0  # Already in PATH
    else
        return 1  # Not in PATH
    fi
}

setup_path() {
    # Guide user to add ~/.local/bin to PATH if needed
    if check_path; then
        return 0
    fi
    
    echo ""
    print_warning "~/.local/bin is not in your PATH"
    echo ""
    print_info "To use 'connectify' command, add this to your shell profile:"
    echo ""
    
    # Detect shell
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_RC="$HOME/.zshrc"
        echo '  echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.zshrc'
        echo '  source ~/.zshrc'
    elif [[ "$SHELL" == *"bash"* ]]; then
        SHELL_RC="$HOME/.bashrc"
        echo '  echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
        echo '  source ~/.bashrc'
    else
        echo '  export PATH="$HOME/.local/bin:$PATH"'
        echo "  (Add to your shell profile)"
    fi
    
    echo ""
    read -p "Would you like me to add it automatically? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ "$SHELL" == *"zsh"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
            print_success "Added to ~/.zshrc"
            print_info "Run: source ~/.zshrc"
        elif [[ "$SHELL" == *"bash"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
            print_success "Added to ~/.bashrc"
            print_info "Run: source ~/.bashrc"
        fi
        echo ""
        print_info "Or open a new terminal window"
    else
        print_info "You'll need to add it manually to use 'connectify' command"
    fi
    
    echo ""
}

detect_architecture() {
    ARCH=$(uname -m)
    if [[ "$ARCH" == "arm64" ]]; then
        echo "arm64"
    elif [[ "$ARCH" == "x86_64" ]]; then
        echo "amd64"
    else
        print_error "Unsupported architecture: $ARCH"
        exit 1
    fi
}

download_binary() {
    local arch=$1
    
    print_info "Downloading Connectify for macOS ($arch)..."
    
    # Create temp directory
    mkdir -p "$TEMP_DIR"
    cd "$TEMP_DIR"
    
    # Determine download URL
    if [[ "$VERSION" == "latest" ]]; then
        DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/latest/download/connectify-macos-${arch}.tar.gz"
    else
        DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}/connectify-macos-${arch}.tar.gz"
    fi
    
    # Download with progress
    if command -v curl &> /dev/null; then
        if ! curl -fL --progress-bar "$DOWNLOAD_URL" -o connectify.tar.gz; then
            print_error "Failed to download Connectify"
            print_info "URL: $DOWNLOAD_URL"
            print_info ""
            print_info "This might mean:"
            print_info "  1. No release has been published yet"
            print_info "  2. The release doesn't have the binary for your architecture"
            print_info ""
            print_info "For development installation, use:"
            print_info "  ./dev-install.sh"
            exit 1
        fi
    else
        print_error "curl is required but not found"
        exit 1
    fi
    
    print_success "Downloaded successfully"
}

extract_binary() {
    print_info "Extracting..."
    
    if ! tar -xzf connectify.tar.gz; then
        print_error "Failed to extract archive"
        exit 1
    fi
    
    if [[ ! -d "connectify" ]] || [[ ! -f "connectify/connectify" ]]; then
        print_error "Invalid archive structure"
        exit 1
    fi
    
    print_success "Extracted successfully"
}

install_binary() {
    print_info "Installing to $LIB_DIR..."
    
    # Remove old installation
    if [[ -d "$LIB_DIR" ]]; then
        rm -rf "$LIB_DIR"
    fi
    
    # Create directories
    mkdir -p "$LIB_DIR"
    mkdir -p "$INSTALL_DIR"
    
    # Copy files
    cp -R connectify/* "$LIB_DIR/"
    chmod +x "$LIB_DIR/connectify"
    
    # Create or update symlink
    if [[ -L "$INSTALL_DIR/connectify" ]] || [[ -f "$INSTALL_DIR/connectify" ]]; then
        rm -f "$INSTALL_DIR/connectify"
    fi
    ln -s "$LIB_DIR/connectify" "$INSTALL_DIR/connectify"
    
    print_success "Installed to $INSTALL_DIR/connectify"
}

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

verify_installation() {
    print_info "Verifying installation..."
    
    if [[ ! -f "$INSTALL_DIR/connectify" ]]; then
        print_error "Installation verification failed - connectify not found"
        exit 1
    fi
    
    print_success "Files installed successfully"
}

setup_autostart() {
    echo ""
    print_info "Auto-Start Configuration"
    echo ""
    echo "Would you like Connectify UI server to start automatically when you log in?"
    echo "This will create a LaunchAgent that starts the UI server in the background."
    echo ""
    read -p "Setup auto-start? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setting up auto-start..."
        
        mkdir -p ~/Library/LaunchAgents
        
        # Create plist with full path (LaunchAgent doesn't support ~ or $HOME)
        cat > ~/Library/LaunchAgents/com.connectify.ui.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.connectify.ui</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.local/bin/connectify</string>
        <string>ui</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/connectify-autostart.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/connectify-autostart.error.log</string>
</dict>
</plist>
EOF
        
        launchctl load ~/Library/LaunchAgents/com.connectify.ui.plist 2>/dev/null || true
        sleep 2
        
        if lsof -i :7890 >/dev/null 2>&1; then
            print_success "Auto-start configured and UI server is now running!"
            print_info "UI is available at: http://localhost:7890"
        else
            print_success "Auto-start configured!"
            print_info "UI server will start automatically on next login"
        fi
        
        echo ""
        print_info "To disable auto-start later, run:"
        echo "  launchctl unload ~/Library/LaunchAgents/com.connectify.ui.plist"
        echo ""
    else
        print_info "Skipping auto-start setup"
        print_info "You can start the UI server manually with: connectify ui start"
        echo ""
    fi
}

print_post_install() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║        🎉 Connectify installed successfully! 🎉              ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    print_info "Get started with these commands:"
    echo ""
    echo "  connectify                    # Launch SSH connection manager"
    echo "  connectify --add              # Add a new SSH host"
    echo "  connectify --list             # List all hosts"
    echo "  connectify ui start           # Start background UI server"
    echo "  connectify --help             # Show all options"
    echo ""
    print_info "Configuration file: ~/.ssh_manager_config.json"
    print_info "UI will be available at: http://localhost:7890"
    echo ""
    print_success "Happy connecting! 🚀"
    echo ""
}

main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              Connectify Installer                            ║"
    echo "║          SSH Session Manager for macOS                       ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_macos
    check_not_root
    
    ARCH=$(detect_architecture)
    print_info "Detected architecture: $ARCH"
    
    # Set trap to cleanup on exit
    trap cleanup EXIT
    
    download_binary "$ARCH"
    extract_binary
    install_binary
    verify_installation
    setup_path
    setup_autostart
    print_post_install
}

main
