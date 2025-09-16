-- SSH Session Manager UI Launcher for macOS
-- This AppleScript checks if the server is running and launches it if needed

on run
    set scriptPath to "/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/launch_ui.sh"

    try
        -- Run the shell script
        do shell script "bash " & quoted form of scriptPath

        -- Show success notification
        display notification "SSH Session Manager UI opened successfully" with title "SSH Manager" sound name "Glass"

    on error errorMessage
        -- Show error notification
        display notification "Failed to launch SSH Manager: " & errorMessage with title "SSH Manager Error" sound name "Basso"

        -- Optionally show dialog for debugging
        display dialog "Error launching SSH Session Manager:" & return & return & errorMessage buttons {"OK"} default button "OK" with icon stop
    end try
end run
