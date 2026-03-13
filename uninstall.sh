#!/bin/bash
set -e

# Connectify Uninstaller
# Removes Connectify SSH Session Manager from macOS

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/connectify"
CONFIG_DIR="$HOME/.connectify"
CONFIG_FILE="$HOME/.ssh_manager_config.json"

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

# Check if connectify is installed
check_installed() {
    if [[ ! -f "$INSTALL_DIR/connectify" ]] && [[ ! -d "$LIB_DIR" ]]; then
        print_error "Connectify is not installed"
        exit 1
    fi
}

# Stop UI server if running
stop_ui_server() {
    print_info "Checking for running UI server..."
    
    UI_PID=$(lsof -ti :7890 2>/dev/null || true)
    
    if [[ -n "$UI_PID" ]]; then
        print_info "Stopping UI server (PID: $UI_PID)..."
        kill -9 "$UI_PID" 2>/dev/null || true
        sleep 1
        print_success "UI server stopped"
    else
        print_info "No UI server running"
    fi
}

# Remove installed files
remove_files() {
    print_info "Removing Connectify files..."
    
    # Remove symlink
    if [[ -L "$INSTALL_DIR/connectify" ]]; then
        rm -f "$INSTALL_DIR/connectify"
        print_success "Removed $INSTALL_DIR/connectify"
    fi
    
    # Remove library directory
    if [[ -d "$LIB_DIR" ]]; then
        rm -rf "$LIB_DIR"
        print_success "Removed $LIB_DIR"
    fi
    
    # Remove old launch command if it exists (from old system install)
    if [[ -f "/usr/local/bin/launch" ]]; then
        print_info "Found old 'launch' command in /usr/local/bin"
        print_warning "This requires sudo to remove"
        read -p "Remove it? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo rm -f "/usr/local/bin/launch"
            sudo rm -rf "/usr/local/lib/connectify" 2>/dev/null || true
            print_success "Removed old system installation"
        fi
    fi
}

# Ask about config files
remove_config() {
    echo ""
    print_warning "Configuration files found:"
    
    if [[ -d "$CONFIG_DIR" ]]; then
        echo "  - $CONFIG_DIR (logs, PID files)"
    fi
    
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "  - $CONFIG_FILE (SSH host configurations)"
    fi
    
    echo ""
    read -p "Do you want to remove configuration files? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ -d "$CONFIG_DIR" ]]; then
            rm -rf "$CONFIG_DIR"
            print_success "Removed $CONFIG_DIR"
        fi
        
        if [[ -f "$CONFIG_FILE" ]]; then
            rm -f "$CONFIG_FILE"
            print_success "Removed $CONFIG_FILE"
        fi
        
        print_info "All configuration files removed"
    else
        print_info "Configuration files kept"
        print_info "You can manually remove them later:"
        echo "  rm -rf $CONFIG_DIR"
        echo "  rm -f $CONFIG_FILE"
    fi
}

# Clean up keychain entries
clean_keychain() {
    echo ""
    print_warning "Connectify stores SSH passwords in macOS Keychain"
    read -p "Do you want to remove stored passwords from Keychain? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "To remove Keychain entries, open 'Keychain Access' app and search for 'SSH_Manager'"
        print_info "Then manually delete the entries"
        echo ""
        read -p "Press Enter to continue..."
    else
        print_info "Keychain entries kept"
    fi
}

# Verify uninstallation
verify_uninstall() {
    print_info "Verifying uninstallation..."
    
    if [[ -f "$INSTALL_DIR/connectify" ]] || [[ -d "$LIB_DIR" ]]; then
        print_error "Uninstallation verification failed - some files still exist"
        exit 1
    fi
    
    if command -v connectify &> /dev/null; then
        print_error "Uninstallation verification failed - connectify still in PATH"
        exit 1
    fi
    
    print_success "Uninstallation verified"
}

# Main uninstallation flow
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              Connectify Uninstaller                          ║"
    echo "║          SSH Session Manager for macOS                       ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_installed
    
    print_warning "This will remove Connectify from your system"
    read -p "Are you sure you want to uninstall? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstallation cancelled"
        exit 0
    fi
    
    echo ""
    stop_ui_server
    remove_files
    remove_config
    clean_keychain
    verify_uninstall
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║        👋 Connectify has been uninstalled                    ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    print_success "Uninstallation complete!"
    echo ""
    print_info "To reinstall Connectify in the future, run:"
    echo "  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/install.sh | sh"
    echo ""
}

# Run main uninstallation
main
