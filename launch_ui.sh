#!/bin/bash

# SSH Session Manager UI Launcher
# Checks if server is running on port 7890, launches if needed, then opens browser

PORT=7890
URL="http://localhost:$PORT"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_COMMAND="cd $SCRIPT_DIR && uv run python main.py"

# Function to check if port is in use
check_port() {
    lsof -i :$PORT >/dev/null 2>&1
    return $?
}

# Function to wait for server to be ready
wait_for_server() {
    local max_attempts=30
    local attempt=1

    echo "Waiting for server to start..."
    while [ $attempt -le $max_attempts ]; do
        if check_port; then
            echo "Server is ready!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: Server not ready yet..."
        sleep 1
        ((attempt++))
    done

    echo "Timeout: Server did not start within 30 seconds"
    return 1
}

# Function to open or switch to browser tab
open_or_switch_browser() {
    local url="$1"

    # Simple approach - just try Chrome with minimal AppleScript
    if pgrep -x "Google Chrome" > /dev/null 2>&1; then
        osascript -e '
        tell application "Google Chrome"
            repeat with w in windows
                repeat with i from 1 to count of tabs of w
                    if URL of tab i of w contains "localhost:7890" then
                        set active tab index of w to i
                        activate
                        return
                    end if
                end repeat
            end repeat
        end tell' 2>/dev/null && echo "Switched to existing Chrome tab" && return 0
    fi

    # If Chrome didn't work, just open normally
    echo "Opening new tab..."
    open "$url"
}

# Main logic
if check_port; then
    echo "Server is already running on port $PORT"
    echo "Opening browser..."
    open_or_switch_browser "$URL"
else
    echo "Server not running. Starting server..."

    # Launch server in background with silent mode
    nohup bash -c "$LAUNCH_COMMAND --silent" > /dev/null 2>&1 &

    # Wait for server to be ready
    if wait_for_server; then
        echo "Opening browser..."
        open_or_switch_browser "$URL"
    else
        echo "Failed to start server. Please check the logs."
        exit 1
    fi
fi
