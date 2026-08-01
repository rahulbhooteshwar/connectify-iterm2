#!/usr/bin/env python3
"""
Starting the web UI at login.

macOS does this with a LaunchAgent: a plist in ~/Library/LaunchAgents that
launchd loads when you log in. This writes it, loads it, and can tell you
whether it is there and working - which is what `connectify autostart` and the
installer both need.

The plist records the *absolute* path of the connectify binary, because
launchd expands neither `~` nor `$HOME`. That path is resolved when auto-start
is enabled, so moving or reinstalling Connectify elsewhere leaves a
LaunchAgent pointing at nothing; `status()` reports that rather than claiming
everything is fine.
"""

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.connectify.ui"
PLIST_PATH = Path(f"~/Library/LaunchAgents/{LABEL}.plist").expanduser()

# Under ~/Library/Logs, where macOS keeps user logs and Console.app finds
# them. /tmp works, but a persistent job writing there is a shape endpoint
# security tools are trained to distrust.
LOG_DIR = Path("~/Library/Logs/Connectify").expanduser()
STDOUT_LOG = str(LOG_DIR / "autostart.log")
STDERR_LOG = str(LOG_DIR / "autostart.error.log")

# The shell-profile alternative. No login hook at all: the server comes up the
# first time you open a terminal. On a managed Mac that is often the difference
# between working and being quarantined - endpoint security watches LaunchAgents
# closely, and rightly, because that is where persistence lives.
BEGIN_MARK = "# >>> connectify autostart >>>"
END_MARK = "# <<< connectify autostart <<<"

SHELL_PROFILES = {
    'zsh': "~/.zshrc",
    # macOS terminals open login shells, which read this one
    'bash': "~/.bash_profile",
    'fish': "~/.config/fish/config.fish",
}


def connectify_binary():
    """The command launchd should run, as an absolute path.

    Prefers what is on PATH, then the usual install location, then - running
    from a source checkout - however this process was started.
    """
    found = shutil.which("connectify")
    if found:
        return str(Path(found).resolve())

    installed = Path("~/.local/bin/connectify").expanduser()
    if installed.exists():
        return str(installed.resolve())

    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).resolve())

    return None


def shell_name():
    """Which shell the user is in, as far as $SHELL knows."""
    return Path(os.environ.get('SHELL', '')).name or None


def shell_profile():
    """The rc file to write into, or None for a shell we don't know."""
    profile = SHELL_PROFILES.get(shell_name())
    return Path(profile).expanduser() if profile else None


def _shell_block():
    """The lines we manage, between markers so they can be taken out again."""
    note = ("# Starts the Connectify web UI in the background if it is not already\n"
            "# running. Remove with: connectify autostart disable --shell")

    if shell_name() == 'fish':
        body = ("if command -v connectify >/dev/null 2>&1\n"
                "    connectify ui start >/dev/null 2>&1 &\n"
                "end")
    else:
        # Backgrounded: `ui start` waits for the server to answer, and no one
        # wants their terminal to pause for that
        body = "command -v connectify >/dev/null 2>&1 && (connectify ui start >/dev/null 2>&1 &)"

    return f"{BEGIN_MARK}\n{note}\n{body}\n{END_MARK}\n"


def _without_block(text):
    """The file's contents with any block we previously wrote removed."""
    if BEGIN_MARK not in text:
        return text, False

    before, rest = text.split(BEGIN_MARK, 1)
    after = rest.split(END_MARK, 1)[1] if END_MARK in rest else ''
    return (before.rstrip('\n') + ('\n' if before.strip() else '')
            + after.lstrip('\n'), True)


def shell_status():
    """Whether the rc file currently starts the server."""
    profile = shell_profile()
    if not profile:
        return {'supported': False, 'configured': False, 'profile': None}

    try:
        configured = BEGIN_MARK in profile.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        configured = False

    return {'supported': True, 'configured': configured, 'profile': str(profile)}


def enable_shell():
    """Add the block to the shell profile. Returns (ok, message)."""
    profile = shell_profile()
    if not profile:
        return False, (f"Don't know where {shell_name() or 'this shell'} keeps its "
                       f"startup file. Add this line to it yourself:\n"
                       f"    connectify ui start >/dev/null 2>&1 &")

    try:
        existing = profile.read_text(encoding='utf-8') if profile.exists() else ''
        cleaned, _ = _without_block(existing)
        if cleaned and not cleaned.endswith('\n'):
            cleaned += '\n'

        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(cleaned + ('\n' if cleaned else '') + _shell_block(),
                           encoding='utf-8')
    except OSError as e:
        return False, f"Could not write {profile}: {e}"

    return True, (f"Added to {profile} - the web UI will start with your first "
                  f"terminal. No LaunchAgent, so nothing to flag as persistence.")


def disable_shell():
    """Take the block back out. Returns (ok, message)."""
    profile = shell_profile()
    if not profile or not profile.exists():
        return True, "Nothing to remove"

    try:
        text = profile.read_text(encoding='utf-8')
        cleaned, found = _without_block(text)
        if not found:
            return True, f"{profile} does not start Connectify"
        profile.write_text(cleaned, encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return False, f"Could not edit {profile}: {e}"

    return True, f"Removed from {profile}"


def _launchctl(*args, check=False):
    try:
        return subprocess.run(['launchctl', *args], capture_output=True,
                              text=True, timeout=15, check=check)
    except (OSError, subprocess.SubprocessError):
        return None


def is_loaded():
    """True when launchd currently knows about the agent."""
    result = _launchctl('print', f'gui/{os.getuid()}/{LABEL}')
    if result is not None and result.returncode == 0:
        return True

    # Older macOS: `launchctl print` may not be available
    listing = _launchctl('list')
    return bool(listing and listing.returncode == 0 and LABEL in listing.stdout)


def configured_program():
    """The binary the installed LaunchAgent points at, if there is one."""
    if not PLIST_PATH.exists():
        return None
    try:
        with open(PLIST_PATH, 'rb') as f:
            arguments = plistlib.load(f).get('ProgramArguments') or []
        return arguments[0] if arguments else None
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None


def status():
    """Everything a caller needs to describe the current state."""
    program = configured_program()
    return {
        'supported': sys.platform == 'darwin',
        'configured': PLIST_PATH.exists(),
        'loaded': is_loaded() if PLIST_PATH.exists() else False,
        'plist': str(PLIST_PATH),
        'program': program,
        # A LaunchAgent pointing at a binary that has moved will fail silently
        # at every login, so it is worth calling out
        'stale': bool(program and not Path(program).exists()),
        'shell': shell_status(),
    }


def describe(state=None):
    """One line for the diagnostics and the installer."""
    state = state or status()

    shell = state.get('shell') or {}

    if not state['supported']:
        return "not applicable on this platform"
    if not state['configured']:
        if shell.get('configured'):
            return f"started from {shell['profile']} (no LaunchAgent)"
        return "not set up - run 'connectify autostart enable'"
    if state['stale']:
        return (f"points at {state['program']}, which no longer exists - "
                f"run 'connectify autostart enable' to repair")
    if not state['loaded']:
        return "set up but not loaded - run 'connectify autostart enable'"
    return "enabled"


def _plist_bytes(program):
    """The LaunchAgent, written to look like what it is: one background job.

    Two things matter here, and they are the same thing twice.

    ``connectify --silent`` is the server itself, running in the foreground.
    The obvious alternative, ``connectify ui start``, spawns the server and
    exits straight away - so launchd sees the job finish, and with KeepAlive
    it starts it again, every ten seconds, forever. A process respawning on a
    timer under a login-persistence entry is close to the textbook shape of
    something malicious, and endpoint security tools flag it as such. It is
    also simply wrong: launchd should supervise the server, not a launcher.

    KeepAlive is off for the same reason. RunAtLoad starts the server once
    when you log in, which is what "start at login" means; nothing restarts
    it behind your back, and `connectify ui stop` stays meaningful.
    """
    return plistlib.dumps({
        'Label': LABEL,
        'ProgramArguments': [program, '--silent'],
        'RunAtLoad': True,
        'KeepAlive': False,
        'StandardOutPath': STDOUT_LOG,
        'StandardErrorPath': STDERR_LOG,
    })


def enable():
    """Write the LaunchAgent and load it. Returns (ok, message)."""
    if sys.platform != 'darwin':
        return False, "Auto-start uses launchd, which is macOS only"

    program = connectify_binary()
    if not program:
        return False, ("Could not find the connectify command. Install it first, "
                       "or make sure ~/.local/bin is on your PATH.")

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.write_bytes(_plist_bytes(program))
    except OSError as e:
        return False, f"Could not write {PLIST_PATH}: {e}"

    # Replace any previous registration, so re-running this repairs a stale one
    _launchctl('bootout', f'gui/{os.getuid()}/{LABEL}')
    _launchctl('unload', str(PLIST_PATH))

    loaded = _launchctl('bootstrap', f'gui/{os.getuid()}', str(PLIST_PATH))
    if not loaded or loaded.returncode != 0:
        loaded = _launchctl('load', str(PLIST_PATH))

    if not loaded or loaded.returncode != 0:
        detail = (loaded.stderr or loaded.stdout).strip() if loaded else 'launchctl not available'
        return False, f"Wrote {PLIST_PATH} but launchd would not load it: {detail}"

    return True, f"Auto-start enabled - the web UI server starts when you log in"


def disable():
    """Unload the LaunchAgent and remove it. Returns (ok, message)."""
    if not PLIST_PATH.exists():
        return True, "Auto-start was not set up"

    _launchctl('bootout', f'gui/{os.getuid()}/{LABEL}')
    _launchctl('unload', str(PLIST_PATH))

    try:
        PLIST_PATH.unlink()
    except OSError as e:
        return False, f"Could not remove {PLIST_PATH}: {e}"

    return True, "Auto-start disabled - start the server with 'connectify ui start'"
