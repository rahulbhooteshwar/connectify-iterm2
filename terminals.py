#!/usr/bin/env python3
"""
Opening a terminal tab and running a session in it.

Connectify prepares each SSH session as a self-contained script (see
``ssh_session.py``) and then needs exactly one thing from a terminal emulator:
run this script, in a new tab, with this title. That is the whole contract, and
it is small enough that a second terminal costs little.

Two backends implement it:

* **iTerm2** - the one Connectify is built around. It can run a command *as* the
  session, so nothing is ever typed into a shell, and it has profiles, badges
  and per-host colours. Recommended.
* **macOS Terminal** - always present, so Connectify works on a machine with
  nothing installed. Basic launching only: no profiles, and two rough edges
  worth knowing about, both documented on ``AppleTerminalBackend``.

Which one is used comes from :func:`resolve`. Everything here is best-effort on
a non-macOS box (e.g. CI): detection returns None rather than raising.
"""

import os
import shlex
import subprocess
import time
from typing import NamedTuple

import iterm_profiles

# Config values for the `terminal` preference, and for CONNECTIFY_TERMINAL
AUTO = 'auto'
ITERM2 = 'iterm2'
APPLE_TERMINAL = 'terminal'

CHOICES = (AUTO, ITERM2, APPLE_TERMINAL)

APPLE_TERMINAL_BUNDLE_ID = "com.apple.Terminal"
APPLE_TERMINAL_APP_NAME = "Terminal.app"

# Terminal.app has lived in /System/Applications since Catalina moved the
# read-only system volume; the older path is kept for anything before that.
APPLE_TERMINAL_SEARCH_PATHS = [
    "/System/Applications/Utilities",
    "/Applications/Utilities",
]

ITERM_DOWNLOAD_URL = iterm_profiles.ITERM_DOWNLOAD_URL


# How the macOS Terminal ended up placing a session. Only NO_TAB means
# something the user can fix: windows were open, but the tab keystroke did
# nothing, which is what a missing Accessibility permission looks like.
TAB = 'tab'
FIRST_WINDOW = 'window'
NO_TAB = 'notab'


class TerminalLaunchError(RuntimeError):
    """The terminal could not be scripted into opening the session."""


class LaunchResult(NamedTuple):
    """A session that opened, plus anything worth telling the user about it.

    ``notices`` are advisory - the session is already running. Each is
    ``{"kind": "info"|"warning", "text": ...}``, ready for the web UI's toast.
    """

    id: str
    notices: tuple = ()


def _applescript_escape(value):
    """Escape a Python string for embedding in an AppleScript string literal."""
    return str(value).replace('\\', '\\\\').replace('"', '\\"')


class TerminalBackend:
    """What Connectify needs from a terminal emulator."""

    key = None
    display_name = None
    app_name = None

    # True when the backend can be told which profile to open a session with.
    # Also gates installing the bundled profiles: there is no point creating
    # iTerm2's DynamicProfiles folder on a machine that has no iTerm2.
    supports_profiles = False

    def find(self):
        """Path to the application bundle, or None if it isn't installed."""
        raise NotImplementedError

    def is_installed(self):
        return self.find() is not None

    def _probe_script(self):
        """AppleScript that succeeds only if the app is up and answering."""
        raise NotImplementedError

    def is_ready(self):
        """True when the app is running and answering AppleScript."""
        try:
            result = subprocess.run(
                ['osascript', '-e', self._probe_script()],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def ensure_running(self, timeout=20):
        """Make sure the app is up and actually answering before we script it.

        Waiting for a real answer (rather than sleeping a fixed few seconds) is
        what stops the first launch after a cold start from failing.
        """
        if self.is_ready():
            return True

        print(f"📱 {self.display_name} not responding yet, launching it...")
        for launcher in (['open', '-a', self.app_name],
                         ['osascript', '-e',
                          f'tell application "{self.app_name}" to activate']):
            try:
                subprocess.run(launcher, check=True, capture_output=True,
                               text=True, timeout=15)
                break
            except (OSError, subprocess.SubprocessError):
                continue
        else:
            print(f"⚠️  Could not launch {self.display_name}.")
            for line in self.install_hint():
                print(f"   {line}")
            return False

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_ready():
                print(f"✅ {self.display_name} is ready")
                return True
            time.sleep(0.4)

        print(f"⚠️  {self.display_name} did not become ready in time")
        return False

    def open_session(self, command, title, profile=None, debug=False):
        """Open a tab running ``command``, titled ``title``.

        Returns an identifier for the new session - proof that a tab really
        exists rather than an assumption that it does. Raises
        :class:`TerminalLaunchError` if it could not be opened.
        """
        raise NotImplementedError

    # --- guidance ----------------------------------------------------------
    #
    # The installer, `connectify doctor`, `connectify configure` and the launch
    # failure path all have to say the same things about macOS permissions and
    # about iTerm2 being the better experience. They say them from here, so
    # there is one wording to keep right.

    def permission_hint(self):
        """Lines about the macOS permission this backend needs, if any."""
        return []

    def upgrade_hint(self):
        """Lines about getting a better experience, if there is one to get."""
        return []

    def install_hint(self):
        """Lines about installing this backend."""
        return []


class ITerm2Backend(TerminalBackend):
    """iTerm2, scripted through its AppleScript interface.

    The session script is passed as the tab's *command*, so no shell runs it:
    the command never appears in the tab or in the shell history.
    """

    key = ITERM2
    display_name = "iTerm2"
    app_name = "iTerm"
    supports_profiles = True

    def find(self):
        return iterm_profiles.find_iterm2()

    def _probe_script(self):
        return 'tell application "iTerm" to return (count of windows) as string'

    def _create_applescript(self, command, title, profile_name):
        """AppleScript that opens a tab running the launcher directly.

        Explicit tab/window references avoid races when several sessions are
        launched at once, and passing the launcher as the session's command
        means nothing is ever typed into a shell. The script returns the new
        session's id so the caller can confirm the tab really exists.
        """
        escaped_command = _applescript_escape(command)
        escaped_title = _applescript_escape(title)
        with_profile = (f'with profile "{_applescript_escape(profile_name)}"'
                        if profile_name else 'with default profile')
        return f'''
        tell application "iTerm"
            activate
            if (count of windows) = 0 then
                set newWindow to (create window {with_profile} command "{escaped_command}")
                set targetSession to current session of newWindow
            else
                tell current window
                    set newTab to (create tab {with_profile} command "{escaped_command}")
                    set targetSession to current session of newTab
                end tell
            end if
            tell targetSession
                set name to "{escaped_title}"
                return id
            end tell
        end tell
        '''

    def open_session(self, command, title, profile=None, debug=False):
        profile = profile or "Default"

        profiles_to_try = [profile]
        if profile != "Default":
            profiles_to_try.append("Default")
        profiles_to_try.append(None)   # let iTerm2 pick its default profile

        last_error = None
        for profile_attempt in profiles_to_try:
            for attempt in range(2):   # one retry for transient AppleScript errors
                try:
                    script = self._create_applescript(command, title, profile_attempt)
                    result = subprocess.run(
                        ['osascript', '-e', script],
                        check=True, capture_output=True, text=True, timeout=30,
                    )

                    # The script returns the new session's id: proof that the
                    # tab exists rather than an assumption that it does
                    session_id = result.stdout.strip()
                    if not session_id:
                        raise subprocess.CalledProcessError(
                            1, 'osascript',
                            stderr='iTerm2 did not report a session id')

                    notices = ()
                    if profile_attempt != profile:
                        using = profile_attempt or "iTerm2's default profile"
                        print(f"⚠️  Profile '{profile}' not usable, used {using} instead")
                        notices = ({
                            "kind": "warning",
                            "text": f"Profile '{profile}' is not in iTerm2 - "
                                    f"used {using} instead",
                        },)

                    return LaunchResult(session_id, notices)

                except subprocess.TimeoutExpired:
                    last_error = "iTerm2 did not respond in time"
                    break
                except subprocess.CalledProcessError as e:
                    last_error = (e.stderr or str(e)).strip()
                    if attempt == 0 and _is_transient_applescript_error(last_error):
                        time.sleep(0.5)
                        continue
                    break

            if debug:
                print(f"DEBUG: profile '{profile_attempt}' failed: {last_error}")

        raise TerminalLaunchError(last_error or "iTerm2 did not open a session")

    def permission_hint(self):
        return [
            "iTerm2 must be allowed to be controlled by Connectify:",
            "System Settings > Privacy & Security > Automation",
        ]

    def install_hint(self):
        return [f"Make sure iTerm2 is installed: {ITERM_DOWNLOAD_URL}"]


class AppleTerminalBackend(TerminalBackend):
    """The Terminal that ships with macOS.

    Basic launching only, with two rough edges Terminal.app forces on us:

    **Tabs need permission.** Terminal's AppleScript dictionary has no "create
    tab" command - ``do script`` opens a new *window*. A real tab needs a Cmd-T
    keystroke sent through System Events, which needs Accessibility permission.
    Without it each session opens in its own window, which is a downgrade
    rather than a failure, so it is never treated as an error.

    **The command is typed into a shell.** Terminal cannot run a command *as*
    the session the way iTerm2 can, so the launcher's path lands in the tab's
    scrollback. That path is not a secret (see ``ssh_session``'s module
    docstring) and the launcher deletes its own directory before handing back a
    shell. Because the launcher is ``exec``'d, the shell it replaces normally
    never writes its history file either - though that depends on the user's
    shell configuration, so it is a nicety rather than a guarantee. Passwords
    and passphrases are unaffected: they travel through the same private FIFO
    on both backends, never through the terminal.
    """

    key = APPLE_TERMINAL
    display_name = "macOS Terminal"
    app_name = "Terminal"
    supports_profiles = False

    def find(self):
        return iterm_profiles.find_app(
            APPLE_TERMINAL_BUNDLE_ID, APPLE_TERMINAL_APP_NAME,
            search_paths=APPLE_TERMINAL_SEARCH_PATHS,
        )

    def _probe_script(self):
        return 'tell application "Terminal" to return (count of windows) as string'

    def _create_applescript(self, command, title):
        """AppleScript that opens a tab (or a window) and runs the launcher.

        ``exec`` replaces the tab's login shell, so the launcher owns the tab;
        the launcher's own tail hands a shell back once ssh exits.

        The keystroke is wrapped in a ``try`` and confirmed by counting tabs
        before and after. That guard is what makes the fallback safe: if System
        Events is not authorised, or the keystroke simply does nothing, we open
        a new window instead. Without it, ``do script ... in selected tab of
        front window`` would run ssh inside whatever the user was already doing
        in that tab.

        Returns ``<outcome> <tty>``. The outcome distinguishes a window we
        opened because there was nothing to add a tab to (fine, expected) from
        one we fell back to because the keystroke did nothing (worth telling
        the user about - it means the Accessibility permission is missing).
        """
        escaped_command = _applescript_escape(f"exec {shlex.quote(str(command))}")
        escaped_title = _applescript_escape(title)
        return f'''
        tell application "Terminal"
            activate
            set didTab to false
            set hadWindows to (count of windows) > 0
            if hadWindows then
                set tabCount to count of tabs of front window
                try
                    tell application "System Events" to tell process "Terminal" to keystroke "t" using command down
                    repeat 20 times
                        delay 0.05
                        if (count of tabs of front window) > tabCount then
                            set didTab to true
                            exit repeat
                        end if
                    end repeat
                end try
            end if

            if didTab then
                set newTab to do script "{escaped_command}" in selected tab of front window
                set outcome to "{TAB}"
            else
                set newTab to do script "{escaped_command}"
                if hadWindows then
                    set outcome to "{NO_TAB}"
                else
                    set outcome to "{FIRST_WINDOW}"
                end if
            end if

            set custom title of newTab to "{escaped_title}"
            return outcome & " " & tty of newTab
        end tell
        '''

    def open_session(self, command, title, profile=None, debug=False):
        # `profile` is accepted and ignored: Terminal has its own "settings
        # sets", but they are not iTerm2 profiles and mapping one onto the
        # other by name would silently do the wrong thing.
        last_error = None
        for attempt in range(2):   # one retry for transient AppleScript errors
            try:
                script = self._create_applescript(command, title)
                result = subprocess.run(
                    ['osascript', '-e', script],
                    check=True, capture_output=True, text=True, timeout=30,
                )

                # Terminal tabs have no id, so the tty is what proves a tab
                # really appeared - /dev/ttys004 and friends
                outcome, _, tty = result.stdout.strip().partition(' ')
                if not tty:
                    raise subprocess.CalledProcessError(
                        1, 'osascript',
                        stderr='Terminal did not report a tty for the new tab')

                return LaunchResult(tty, self._notices_for(outcome))

            except subprocess.TimeoutExpired:
                last_error = "Terminal did not respond in time"
                break
            except subprocess.CalledProcessError as e:
                last_error = (e.stderr or str(e)).strip()
                if attempt == 0 and _is_transient_applescript_error(last_error):
                    time.sleep(0.5)
                    continue
                break

        if debug:
            print(f"DEBUG: Terminal launch failed: {last_error}")

        raise TerminalLaunchError(last_error or "Terminal did not open a session")

    @staticmethod
    def _notices_for(outcome):
        """What to tell the user about where their session landed.

        Every session says which terminal it opened in, because "why doesn't
        this look like my iTerm2 profile?" is the obvious first question. Only
        a genuine tab failure adds the fix - a window opened because Terminal
        had none is normal and needs no advice.
        """
        if outcome == NO_TAB:
            return ({
                "kind": "warning",
                "text": "Opened in a new macOS Terminal window - allow Connectify "
                        "under Privacy & Security › Accessibility to get tabs",
            },)
        return ({"kind": "info", "text": "Opened in the macOS Terminal"},)

    def permission_hint(self):
        # Two different permissions, and they fail differently: without
        # Automation no session opens at all, without Accessibility they open
        # but land in windows instead of tabs.
        return [
            "Terminal must be allowed to be controlled by Connectify:",
            "System Settings > Privacy & Security > Automation",
            "Opening sessions as tabs additionally needs:",
            "System Settings > Privacy & Security > Accessibility",
            "Without that one every session opens in a new window instead.",
        ]

    def upgrade_hint(self):
        return [
            "Connectify works best with iTerm2 - it adds profiles, badges and",
            f"per-host colours: {ITERM_DOWNLOAD_URL}",
            "Already installed it? Run: connectify configure iterm",
        ]


def _is_transient_applescript_error(message):
    """Errors worth one retry: the app is busy, starting up or mid-redraw."""
    message = (message or '').lower()
    return any(marker in message for marker in (
        'timed out', 'not responding', "can't get current window",
        'invalid index', '-1712', '-1728', '-600',
    ))


# --- picking a backend -------------------------------------------------------

# Detection shells out to osascript with a 10s timeout, and resolve() sits on
# the launch path, so the answer is remembered for the life of the process.
_detection_cache = {}


def reset_cache():
    """Forget cached app detection - after installing iTerm2, or in tests."""
    _detection_cache.clear()


def _iterm2_installed():
    if 'iterm2' not in _detection_cache:
        _detection_cache['iterm2'] = iterm_profiles.find_iterm2()
    return _detection_cache['iterm2']


def normalize(preference):
    """A usable preference value, or ``auto`` for anything unrecognised."""
    value = str(preference or '').strip().lower()
    return value if value in CHOICES else AUTO


def resolve(preference=None, quiet=True):
    """Decide which terminal to launch sessions in.

    Precedence: the configured preference, then ``CONNECTIFY_TERMINAL``, then
    auto-detection. Auto prefers iTerm2 and falls back to the Terminal that
    ships with macOS, so Connectify works on a machine with nothing installed.

    Returns ``(backend, reason)``, where reason explains the choice well enough
    for ``connectify doctor`` to print it.
    """
    configured = str(preference or '').strip().lower()
    env = str(os.environ.get('CONNECTIFY_TERMINAL', '')).strip().lower()

    wanted, source = AUTO, 'auto'
    if configured:
        wanted, source = normalize(configured), 'configured'
        if wanted == AUTO and configured != AUTO and not quiet:
            print(f"⚠️  Unknown terminal '{configured}' in the config, using auto-detection")
    elif env:
        wanted, source = normalize(env), 'CONNECTIFY_TERMINAL'
        if wanted == AUTO and env != AUTO and not quiet:
            print(f"⚠️  Unknown CONNECTIFY_TERMINAL='{env}', using auto-detection")

    if wanted == ITERM2:
        if _iterm2_installed():
            return ITerm2Backend(), f"{source}: iterm2"
        # A preference should never brick the app - say so and carry on
        if not quiet:
            print("⚠️  iTerm2 is configured but not installed - using macOS Terminal")
            print(f"   Install it from {ITERM_DOWNLOAD_URL}, then: connectify configure iterm")
        return AppleTerminalBackend(), f"{source}: iterm2, but iTerm2 is not installed"

    if wanted == APPLE_TERMINAL:
        return AppleTerminalBackend(), f"{source}: terminal"

    if _iterm2_installed():
        return ITerm2Backend(), "auto: iTerm2 is installed"
    return AppleTerminalBackend(), "auto: iTerm2 is not installed"


def describe(preference=None):
    """A summary of the terminal situation, for doctor and configure."""
    backend, reason = resolve(preference)
    return {
        "backend": backend,
        "key": backend.key,
        "display_name": backend.display_name,
        "reason": reason,
        "path": backend.find(),
        "supports_profiles": backend.supports_profiles,
        "iterm2": _iterm2_installed(),
        "preference": normalize(preference) if preference else AUTO,
    }
