#!/bin/bash

# SSH Session Manager UI Launcher
# Checks if server is running on port 7890, launches if needed, then opens browser

PORT=7890
URL="http://localhost:$PORT"
LAUNCH_PATH="/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/dist/launch"

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

# Main logic
if check_port; then
    echo "Server is already running on port $PORT"
    echo "Opening browser..."
    open "$URL"
else
    echo "Server not running. Starting server..."

    # Launch server in background with silent mode
    nohup "$LAUNCH_PATH" --silent > /dev/null 2>&1 &

    # Wait for server to be ready
    if wait_for_server; then
        echo "Opening browser..."
        open "$URL"
    else
        echo "Failed to start server. Please check the logs."
        exit 1
    fi
fi
