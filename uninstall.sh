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
CONFIG_FILE="$HOME/.connectify/hosts.json"
OLD_CONFIG_FILE="$HOME/.ssh_manager_config.json"
LAUNCHAGENT_PLIST="$HOME/Library/LaunchAgents/com.connectify.ui.plist"

# Parse command line arguments
REMOVE_CONFIG=false
REMOVE_KEYCHAIN=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --remove-config)
            REMOVE_CONFIG=true
            ;;
        --remove-keychain)
            REMOVE_KEYCHAIN=true
            ;;
        --force)
            FORCE=true
            ;;
        --help)
            echo "Usage: uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --remove-config      Also remove configuration files"
            echo "  --remove-keychain    Show instructions to remove keychain entries"
            echo "  --force              Skip confirmation prompt"
            echo "  --help               Show this help message"
            exit 0
            ;;
    esac
done

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
    
    # Stop LaunchAgent if it exists
    if [[ -f "$LAUNCHAGENT_PLIST" ]]; then
        print_info "Stopping LaunchAgent..."
        launchctl unload "$LAUNCHAGENT_PLIST" 2>/dev/null || true
        sleep 1
    fi
    
    # Kill any remaining processes on port 7890
    UI_PID=$(lsof -ti :7890 2>/dev/null || true)
    
    if [[ -n "$UI_PID" ]]; then
        print_info "Stopping UI server (PID: $UI_PID)..."
        kill -9 $UI_PID 2>/dev/null || true
        sleep 1
        print_success "UI server stopped"
    else
        print_info "No UI server running"
    fi
    
    # Remove LaunchAgent plist
    if [[ -f "$LAUNCHAGENT_PLIST" ]]; then
        rm -f "$LAUNCHAGENT_PLIST"
        print_success "Removed LaunchAgent configuration"
    fi
}

# Remove installed files
remove_files() {
    print_info "Removing Connectify files..."
    
    # Remove symlink or binary
    if [[ -f "$INSTALL_DIR/connectify" ]] || [[ -L "$INSTALL_DIR/connectify" ]]; then
        rm -f "$INSTALL_DIR/connectify"
        print_success "Removed $INSTALL_DIR/connectify"
    fi
    
    # Remove library directory
    if [[ -d "$LIB_DIR" ]]; then
        rm -rf "$LIB_DIR"
        print_success "Removed $LIB_DIR"
    fi
    
    # Check for old system installation
    if [[ -f "/usr/local/bin/launch" ]] || [[ -d "/usr/local/lib/connectify" ]]; then
        echo ""
        print_warning "Found old system-wide installation in /usr/local/bin"
        print_info "To remove it, run:"
        echo "  sudo rm -f /usr/local/bin/launch"
        echo "  sudo rm -rf /usr/local/lib/connectify"
        echo ""
    fi
}

# Remove config files if requested
remove_config() {
    if [[ "$REMOVE_CONFIG" == "true" ]]; then
        echo ""
        print_info "Removing configuration files..."
        
        if [[ -d "$CONFIG_DIR" ]]; then
            rm -rf "$CONFIG_DIR"
            print_success "Removed $CONFIG_DIR"
        fi
        
        if [[ -f "$CONFIG_FILE" ]]; then
            rm -f "$CONFIG_FILE"
            print_success "Removed $CONFIG_FILE"
        fi
        
        # Also remove old config file if it exists
        if [[ -f "$OLD_CONFIG_FILE" ]]; then
            rm -f "$OLD_CONFIG_FILE"
            print_success "Removed $OLD_CONFIG_FILE"
        fi
    else
        # Check if config files exist and inform user
        if [[ -d "$CONFIG_DIR" ]] || [[ -f "$CONFIG_FILE" ]] || [[ -f "$OLD_CONFIG_FILE" ]]; then
            echo ""
            print_info "Configuration files preserved:"
            [[ -d "$CONFIG_DIR" ]] && echo "  - $CONFIG_DIR/ (hosts.json, logs, PID files)"
            [[ -f "$OLD_CONFIG_FILE" ]] && echo "  - $OLD_CONFIG_FILE (old config, can be removed)"
            echo ""
            print_info "To remove them, run:"
            echo "  rm -rf $CONFIG_DIR"
            [[ -f "$OLD_CONFIG_FILE" ]] && echo "  rm -f $OLD_CONFIG_FILE"
            echo ""
        fi
    fi
}

# Show keychain cleanup instructions if requested
clean_keychain() {
    if [[ "$REMOVE_KEYCHAIN" == "true" ]]; then
        echo ""
        print_warning "Keychain Cleanup"
        print_info "Connectify stores SSH passwords in macOS Keychain"
        print_info "To remove them:"
        echo "  1. Open 'Keychain Access' app"
        echo "  2. Search for 'SSH_Manager'"
        echo "  3. Delete the entries"
        echo ""
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
    
    # When piped (curl | sh), stdin is not available for interactive prompts
    # So we proceed with uninstallation automatically
    if [[ "$FORCE" != "true" ]] && [[ -t 0 ]]; then
        # Only prompt if running interactively (not piped)
        print_warning "This will remove Connectify from your system"
        read -p "Are you sure you want to uninstall? (y/N): " -n 1 -r
        echo ""
        
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Uninstallation cancelled"
            exit 0
        fi
        echo ""
    else
        print_warning "Uninstalling Connectify..."
        echo ""
    fi
    
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
    
    if [[ "$REMOVE_CONFIG" != "true" ]] && ([[ -d "$CONFIG_DIR" ]] || [[ -f "$CONFIG_FILE" ]]); then
        print_info "Configuration files were preserved"
        print_info "To remove them, run:"
        echo "  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/uninstall.sh | sh -s -- --remove-config"
        echo ""
    fi
    
    print_info "To reinstall Connectify, run:"
    echo "  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/install.sh | sh"
    echo ""
}

# Run main uninstallation
main
