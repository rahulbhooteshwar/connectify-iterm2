#!/bin/bash
# One-liner launcher for SSH Manager - checks port, launches if needed, opens browser
lsof -i :7890 >/dev/null 2>&1 && open "http://localhost:7890" || (nohup "/Users/rahul.bhooteshwar/dev/iterm2-ssh-session-manager/dist/launch" --silent >/dev/null 2>&1 & sleep 3 && open "http://localhost:7890")
