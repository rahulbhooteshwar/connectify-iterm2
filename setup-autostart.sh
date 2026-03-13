#!/bin/bash
set -e

# Connectify Auto-Start Setup
# Configures Connectify UI server to start automatically on login

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PLIST_FILE="$HOME/Library/LaunchAgents/com.connectify.ui.plist"

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
    if ! command -v connectify &> /dev/null; then
        print_error "Connectify is not installed"
        print_info "Install it first with:"
        echo "  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/install.sh | sh"
        exit 1
    fi
}

# Check current status
check_status() {
    if [[ -f "$PLIST_FILE" ]]; then
        if launchctl list | grep -q "com.connectify.ui"; then
            return 0  # Loaded
        else
            return 1  # File exists but not loaded
        fi
    else
        return 2  # Not configured
    fi
}

# Enable auto-start
enable_autostart() {
    print_info "Enabling auto-start for Connectify UI server..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p ~/Library/LaunchAgents
    
    # Create plist file with full path (LaunchAgent doesn't support ~ or $HOME)
    cat > "$PLIST_FILE" << EOF
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
    
    print_success "Created LaunchAgent configuration"
    
    # Load the LaunchAgent
    launchctl load "$PLIST_FILE" 2>/dev/null || true
    
    # Give it a moment to start
    sleep 2
    
    # Check if it started
    if lsof -i :7890 >/dev/null 2>&1; then
        print_success "Auto-start enabled and UI server is now running!"
        print_info "UI is available at: http://localhost:7890"
    else
        print_success "Auto-start enabled!"
        print_info "UI server will start automatically on next login"
    fi
    
    echo ""
    print_info "The UI server will now start automatically when you log in"
    print_info "To disable, run: $0 disable"
}

# Disable auto-start
disable_autostart() {
    print_info "Disabling auto-start for Connectify UI server..."
    
    if [[ ! -f "$PLIST_FILE" ]]; then
        print_warning "Auto-start is not configured"
        return 0
    fi
    
    # Unload the LaunchAgent
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    
    # Remove the plist file
    rm -f "$PLIST_FILE"
    
    print_success "Auto-start disabled"
    print_info "The UI server will no longer start automatically"
    print_info "You can still start it manually with: connectify ui start"
}

# Show current status
show_status() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           Connectify Auto-Start Status                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_status
    local status=$?
    
    if [[ $status -eq 0 ]]; then
        print_success "Auto-start is ENABLED and RUNNING"
        print_info "LaunchAgent: $PLIST_FILE"
        
        if lsof -i :7890 >/dev/null 2>&1; then
            print_info "UI Server: Running on http://localhost:7890"
        else
            print_warning "UI Server: Not running (will start on next login)"
        fi
    elif [[ $status -eq 1 ]]; then
        print_warning "Auto-start is CONFIGURED but NOT LOADED"
        print_info "LaunchAgent: $PLIST_FILE"
        print_info "Run '$0 enable' to load it"
    else
        print_info "Auto-start is NOT CONFIGURED"
        print_info "Run '$0 enable' to set it up"
    fi
    
    echo ""
}

# Show help
show_help() {
    echo "Connectify Auto-Start Setup"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  enable    Enable auto-start (UI server starts on login)"
    echo "  disable   Disable auto-start"
    echo "  status    Show current auto-start status"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 enable     # Enable auto-start"
    echo "  $0 disable    # Disable auto-start"
    echo "  $0 status     # Check current status"
    echo ""
}

# Main function
main() {
    check_installed
    
    case "${1:-enable}" in
        enable)
            enable_autostart
            ;;
        disable)
            disable_autostart
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
