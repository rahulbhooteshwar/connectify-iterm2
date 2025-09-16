#!/bin/bash

# Simplified script for macOS Shortcuts
# Checks if server is running, launches if needed, opens browser

PORT=7890
URL="http://localhost:$PORT"
LAUNCH_PATH="/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/dist/launch"

# Check if port is in use
if lsof -i :$PORT >/dev/null 2>&1; then
    # Server is running, just open browser
    open "$URL"
else
    # Server not running, start it and wait
    nohup "$LAUNCH_PATH" --silent > /dev/null 2>&1 &

    # Wait up to 15 seconds for server to start
    for i in {1..15}; do
        if lsof -i :$PORT >/dev/null 2>&1; then
            sleep 1  # Give it one more second to fully initialize
            open "$URL"
            exit 0
        fi
        sleep 1
    done

    # If we get here, server failed to start
    echo "Failed to start SSH Manager server"
    exit 1
fi
