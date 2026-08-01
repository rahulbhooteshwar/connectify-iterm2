#!/bin/bash
set -e

# Connectify auto-start - kept for the curl|bash URL that used to be the way
# to do this. The work now lives in `connectify autostart`, which knows where
# Connectify is actually installed and can report and repair its state; this
# just forwards to it so there is one implementation rather than two.
#
#   connectify autostart          is it set up?
#   connectify autostart enable   start the web UI at login
#   connectify autostart disable  stop doing that

ACTION="${1:-status}"

if ! command -v connectify >/dev/null 2>&1; then
    printf '\033[0;31m✘\033[0m Connectify is not installed\n'
    printf '  Install it first:\n'
    printf '    curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/install.sh | sh\n'
    exit 1
fi

case "$ACTION" in
    enable|disable|status) ;;
    *)
        printf '\033[0;31m✘\033[0m Unknown action: %s\n' "$ACTION"
        printf '  Usage: %s [enable|disable|status]\n' "$(basename "$0")"
        exit 1
        ;;
esac

printf '\033[2mThis script now forwards to: connectify autostart %s\033[0m\n\n' "$ACTION"
exec connectify autostart "$ACTION"
