#!/bin/bash
set -e

# Connectify Installer
# Installs Connectify SSH Session Manager for macOS

VERSION="1.0.0"
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/connectify"
APP_NAME="connectify"
GITHUB_REPO="rahulbhooteshwar/iterm2-ssh-session-manager"
TEMP_DIR="/tmp/connectify-install"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This installer is only for macOS"
        exit 1
    fi
}

# Check if running as root (we don't want this)
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "Please do not run this installer as root or with sudo"
        print_info "Connectify installs to your home directory and doesn't need sudo"
        exit 1
    fi
}

# Check for required tools
check_dependencies() {
    print_info "Checking dependencies..."
    
    # Check for Python 3.12+
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not found"
        print_info "Install Python 3.12+ from https://www.python.org/downloads/"
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.12"
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
        print_warning "Python 3.12+ is recommended (found Python $PYTHON_VERSION)"
        print_info "Continuing anyway, but you may encounter issues"
    fi
    
    # Check for uv (optional but recommended for development)
    if ! command -v uv &> /dev/null; then
        print_warning "uv not found (optional, only needed for development)"
    fi
    
    print_success "Dependencies check passed"
}

# Detect installation mode (local or remote)
detect_mode() {
    # Check if we're in the source directory
    if [[ -f "$(dirname "$0")/main.py" ]] && [[ -f "$(dirname "$0")/pyproject.toml" ]]; then
        echo "local"
    else
        echo "remote"
    fi
}

# Install from local source
install_local() {
    print_info "Installing from local source..."
    
    SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
    
    # Check if source files exist
    if [[ ! -f "$SOURCE_DIR/main.py" ]]; then
        print_error "main.py not found in $SOURCE_DIR"
        exit 1
    fi
    
    # Build the executable
    print_info "Building Connectify executable..."
    cd "$SOURCE_DIR"
    
    # Check if uv is available
    if command -v uv &> /dev/null; then
        print_info "Using uv to build..."
        uv sync
        uv run pyinstaller connectify.spec
    else
        print_info "Using pip to build..."
        python3 -m pip install --user -q pyinstaller inquirer keyring fastapi uvicorn pydantic
        python3 -m PyInstaller connectify.spec
    fi
    
    if [[ ! -f "$SOURCE_DIR/dist/connectify/connectify" ]]; then
        print_error "Build failed - executable not found"
        exit 1
    fi
    
    print_success "Build completed successfully"
    
    # Install to ~/.local/bin
    print_info "Installing to $INSTALL_DIR..."
    
    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LIB_DIR"
    
    # Remove old installation
    rm -rf "$LIB_DIR"
    
    # Copy files
    mkdir -p "$LIB_DIR"
    cp -R "$SOURCE_DIR/dist/connectify/"* "$LIB_DIR/"
    
    # Create symlink
    rm -f "$INSTALL_DIR/connectify"
    ln -s "$LIB_DIR/connectify" "$INSTALL_DIR/connectify"
    
    # Make executable
    chmod +x "$LIB_DIR/connectify"
    
    print_success "Connectify installed to $INSTALL_DIR/connectify"
}

# Install from remote (GitHub)
install_remote() {
    print_info "Installing from GitHub..."
    
    # Create temp directory
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    # Download release or clone repo
    print_info "Downloading Connectify..."
    
    # Try to download pre-built release first
    RELEASE_URL="https://github.com/${GITHUB_REPO}/releases/latest/download/connectify-macos.tar.gz"
    
    if curl -fsSL "$RELEASE_URL" -o "$TEMP_DIR/connectify.tar.gz" 2>/dev/null; then
        print_info "Downloading pre-built release..."
        cd "$TEMP_DIR"
        tar -xzf connectify.tar.gz
        
        # Install
        mkdir -p "$LIB_DIR"
        rm -rf "$LIB_DIR"
        mkdir -p "$LIB_DIR"
        cp -R connectify/* "$LIB_DIR/"
        
        # Create symlink
        mkdir -p "$INSTALL_DIR"
        rm -f "$INSTALL_DIR/connectify"
        ln -s "$LIB_DIR/connectify" "$INSTALL_DIR/connectify"
        chmod +x "$LIB_DIR/connectify"
        
        print_success "Connectify installed from pre-built release"
    else
        print_info "Pre-built release not found, building from source..."
        
        # Clone repository
        if ! command -v git &> /dev/null; then
            print_error "git is required to install from source"
            exit 1
        fi
        
        git clone "https://github.com/${GITHUB_REPO}.git" "$TEMP_DIR/connectify"
        cd "$TEMP_DIR/connectify"
        
        # Build and install
        if command -v uv &> /dev/null; then
            uv sync
            uv run pyinstaller connectify.spec
        else
            python3 -m pip install --user -q pyinstaller inquirer keyring fastapi uvicorn pydantic
            python3 -m PyInstaller connectify.spec
        fi
        
        # Install
        mkdir -p "$LIB_DIR"
        rm -rf "$LIB_DIR"
        mkdir -p "$LIB_DIR"
        cp -R dist/connectify/* "$LIB_DIR/"
        
        # Create symlink
        mkdir -p "$INSTALL_DIR"
        rm -f "$INSTALL_DIR/connectify"
        ln -s "$LIB_DIR/connectify" "$INSTALL_DIR/connectify"
        chmod +x "$LIB_DIR/connectify"
        
        print_success "Connectify installed from source"
    fi
    
    # Cleanup
    rm -rf "$TEMP_DIR"
}

# Verify installation
verify_installation() {
    print_info "Verifying installation..."
    
    if [[ ! -f "$INSTALL_DIR/connectify" ]]; then
        print_error "Installation verification failed - connectify not found in $INSTALL_DIR"
        exit 1
    fi
    
    if ! command -v connectify &> /dev/null; then
        print_error "Installation verification failed - connectify not in PATH"
        print_info "You may need to add $INSTALL_DIR to your PATH"
        exit 1
    fi
    
    print_success "Installation verified"
}

# Setup auto-start on login
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
        
        # Create LaunchAgents directory if it doesn't exist
        mkdir -p ~/Library/LaunchAgents
        
        # Create plist file
        cat > ~/Library/LaunchAgents/com.connectify.ui.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.connectify.ui</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/connectify</string>
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
        
        # Load the LaunchAgent
        launchctl load ~/Library/LaunchAgents/com.connectify.ui.plist 2>/dev/null || true
        
        # Give it a moment to start
        sleep 2
        
        # Check if it started
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

# Print post-install instructions
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

# Main installation flow
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              Connectify Installer v${VERSION}                   ║"
    echo "║          SSH Session Manager for macOS                       ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_macos
    check_not_root
    check_dependencies
    
    MODE=$(detect_mode)
    
    if [[ "$MODE" == "local" ]]; then
        print_info "Detected local installation mode"
        install_local
    else
        print_info "Detected remote installation mode"
        install_remote
    fi
    
    verify_installation
    setup_autostart
    print_post_install
}

# Run main installation
main
