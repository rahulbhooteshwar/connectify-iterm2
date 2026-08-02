"""Choosing a terminal, and scripting the two Connectify supports.

The iTerm2 hand-off is exercised end to end in test_ssh_session.py; these
cover the backend selection and the macOS Terminal script, which has to open a
tab without ever taking over the one the user is already working in.
"""

import os
import subprocess
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import iterm_profiles
import terminals


@pytest.fixture(autouse=True)
def clean_detection(monkeypatch):
    """Every test states for itself whether iTerm2 is installed."""
    monkeypatch.delenv("CONNECTIFY_TERMINAL", raising=False)
    terminals.reset_cache()
    yield
    terminals.reset_cache()


def with_iterm2(monkeypatch, installed=True):
    monkeypatch.setattr(iterm_profiles, "find_iterm2",
                        lambda: "/Applications/iTerm.app" if installed else None)
    terminals.reset_cache()


# --- picking a backend -------------------------------------------------------

def test_auto_prefers_iterm2_when_it_is_installed(monkeypatch):
    with_iterm2(monkeypatch)

    backend, reason = terminals.resolve()

    assert backend.key == terminals.ITERM2
    assert backend.supports_profiles is True
    assert "iTerm2 is installed" in reason


def test_auto_falls_back_to_the_macos_terminal(monkeypatch):
    """The whole point: Connectify works on a machine with nothing installed."""
    with_iterm2(monkeypatch, installed=False)

    backend, reason = terminals.resolve()

    assert backend.key == terminals.APPLE_TERMINAL
    assert backend.supports_profiles is False
    assert "not installed" in reason


def test_a_configured_preference_beats_auto_detection(monkeypatch):
    with_iterm2(monkeypatch)

    backend, reason = terminals.resolve("terminal")

    assert backend.key == terminals.APPLE_TERMINAL
    assert "configured" in reason


def test_the_env_var_is_used_when_nothing_is_configured(monkeypatch):
    with_iterm2(monkeypatch)
    monkeypatch.setenv("CONNECTIFY_TERMINAL", "terminal")

    backend, reason = terminals.resolve()

    assert backend.key == terminals.APPLE_TERMINAL
    assert "CONNECTIFY_TERMINAL" in reason


def test_the_config_wins_over_the_env_var(monkeypatch):
    with_iterm2(monkeypatch)
    monkeypatch.setenv("CONNECTIFY_TERMINAL", "terminal")

    backend, _ = terminals.resolve("iterm2")

    assert backend.key == terminals.ITERM2


def test_choosing_iterm2_without_iterm2_falls_back_instead_of_breaking(monkeypatch, capsys):
    """A stale preference must never leave the app unable to open a session."""
    with_iterm2(monkeypatch, installed=False)

    backend, reason = terminals.resolve("iterm2", quiet=False)

    assert backend.key == terminals.APPLE_TERMINAL
    assert "not installed" in reason

    output = capsys.readouterr().out
    assert "connectify configure iterm" in output


def test_an_unrecognised_preference_is_treated_as_auto(monkeypatch, capsys):
    with_iterm2(monkeypatch)

    backend, _ = terminals.resolve("kitty", quiet=False)

    assert backend.key == terminals.ITERM2
    assert "Unknown terminal" in capsys.readouterr().out


def test_describe_reports_everything_doctor_prints(monkeypatch):
    with_iterm2(monkeypatch, installed=False)

    info = terminals.describe()

    assert info["display_name"] == "macOS Terminal"
    assert info["supports_profiles"] is False
    assert info["iterm2"] is None
    assert info["reason"]


# --- the macOS Terminal script -----------------------------------------------

def terminal_script(command="/tmp/connectify-run/abc/session.sh", title="prod-web"):
    return terminals.AppleTerminalBackend()._create_applescript(command, title)


def test_the_terminal_script_runs_the_launcher_without_a_shell_command_line():
    script = terminal_script()

    assert "do script" in script
    assert "exec /tmp/connectify-run/abc/session.sh" in script
    # exec replaces the tab's login shell, so the launcher owns the tab
    assert "exec " in script


def test_the_terminal_script_titles_the_tab():
    assert 'set custom title of newTab to "prod-web"' in terminal_script()


def test_the_terminal_script_asks_for_the_tty_as_proof_of_launch():
    """Terminal tabs have no id, so the tty is what proves a tab appeared."""
    assert "tty of newTab" in terminal_script()


def test_the_terminal_script_reports_whether_it_got_a_tab():
    """A window is only worth mentioning when a tab was actually attempted."""
    script = terminal_script()

    assert f'set outcome to "{terminals.TAB}"' in script
    assert f'set outcome to "{terminals.NO_TAB}"' in script
    assert f'set outcome to "{terminals.FIRST_WINDOW}"' in script
    assert "return outcome & \" \" & tty of newTab" in script


def test_the_tab_keystroke_can_fail_without_taking_over_the_current_tab():
    """Without Accessibility permission we must open a window, not hijack a tab."""
    script = terminal_script()

    # The keystroke is optional...
    assert "keystroke \"t\" using command down" in script
    assert "try" in script
    # ...and only believed once a new tab has actually appeared
    assert "set tabCount to count of tabs of front window" in script
    assert "if (count of tabs of front window) > tabCount then" in script
    # Both outcomes are handled, and only the confirmed one targets an existing window
    assert "do script \"exec /tmp/connectify-run/abc/session.sh\" in selected tab of front window" in script
    assert script.count("do script") == 2


def test_the_terminal_script_escapes_quotes_in_the_title():
    script = terminal_script(title='say "hi"')

    assert 'set custom title of newTab to "say \\"hi\\""' in script


def test_a_launcher_path_with_a_space_is_quoted_for_the_shell():
    script = terminal_script(command="/tmp/my runs/session.sh")

    assert "exec '/tmp/my runs/session.sh'" in script


def test_the_terminal_backend_ignores_profiles(monkeypatch):
    """Terminal's 'settings sets' are not iTerm2 profiles - never guess a mapping."""
    backend = terminals.AppleTerminalBackend()
    monkeypatch.setattr(terminals.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'tab /dev/ttys003', ''))

    assert backend.open_session("/tmp/s.sh", "host", profile="connectify-PROD").id == "/dev/ttys003"


def test_the_terminal_backend_fails_loudly_without_a_tty(monkeypatch):
    backend = terminals.AppleTerminalBackend()
    monkeypatch.setattr(terminals.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, '', ''))

    with pytest.raises(terminals.TerminalLaunchError):
        backend.open_session("/tmp/s.sh", "host")


def test_the_terminal_backend_retries_a_transient_error(monkeypatch):
    backend = terminals.AppleTerminalBackend()
    calls = []

    def flaky(argv, **kwargs):
        calls.append(argv)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(
                1, argv, stderr="Terminal got an error: Can't get current window")
        return subprocess.CompletedProcess(argv, 0, 'tab /dev/ttys004', '')

    monkeypatch.setattr(terminals.subprocess, "run", flaky)

    assert backend.open_session("/tmp/s.sh", "host").id == "/dev/ttys004"
    assert len(calls) == 2


# --- what the web UI is told -------------------------------------------------

def open_with_outcome(monkeypatch, outcome):
    backend = terminals.AppleTerminalBackend()
    monkeypatch.setattr(terminals.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(
                            argv, 0, f'{outcome} /dev/ttys003', ''))
    return backend.open_session("/tmp/s.sh", "host")


def test_a_tab_still_says_which_terminal_took_the_session(monkeypatch):
    """'Why doesn't this look like my profile?' is the obvious first question."""
    notices = open_with_outcome(monkeypatch, terminals.TAB).notices

    assert [n["kind"] for n in notices] == ["info"]
    assert "macOS Terminal" in notices[0]["text"]


def test_a_first_window_is_not_reported_as_a_permission_problem(monkeypatch):
    """Terminal had no window to add a tab to - that is normal, not a failure."""
    notices = open_with_outcome(monkeypatch, terminals.FIRST_WINDOW).notices

    assert [n["kind"] for n in notices] == ["info"]
    assert "Accessibility" not in notices[0]["text"]


def test_a_failed_tab_tells_the_user_how_to_get_tabs(monkeypatch):
    notices = open_with_outcome(monkeypatch, terminals.NO_TAB).notices

    assert [n["kind"] for n in notices] == ["warning"]
    assert "Accessibility" in notices[0]["text"]
    assert "window" in notices[0]["text"]


def test_iterm2_says_nothing_when_the_profile_was_honoured(monkeypatch):
    backend = terminals.ITerm2Backend()
    monkeypatch.setattr(terminals.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'sid', ''))

    assert backend.open_session("/tmp/s.sh", "host", profile="connectify-PROD").notices == ()


def test_iterm2_reports_a_profile_it_could_not_use(monkeypatch):
    """The fallback was previously only visible in the server log."""
    backend = terminals.ITerm2Backend()
    calls = []

    def only_default(argv, **kwargs):
        calls.append(argv)
        if 'connectify-PROD' in argv[-1]:
            raise subprocess.CalledProcessError(1, argv, stderr='no such profile')
        return subprocess.CompletedProcess(argv, 0, 'sid', '')

    monkeypatch.setattr(terminals.subprocess, "run", only_default)

    notices = backend.open_session("/tmp/s.sh", "host", profile="connectify-PROD").notices

    assert [n["kind"] for n in notices] == ["warning"]
    assert "connectify-PROD" in notices[0]["text"]


# --- guidance ----------------------------------------------------------------

def test_the_terminal_backend_explains_both_permissions_it_needs():
    """They fail differently: no Automation, no session; no Accessibility, no tabs."""
    hint = " ".join(terminals.AppleTerminalBackend().permission_hint())

    assert "Automation" in hint
    assert "Accessibility" in hint
    assert "new window" in hint, "the fallback has to be described, not just the requirement"


def test_the_terminal_backend_points_at_iterm2_and_the_configure_command():
    hint = " ".join(terminals.AppleTerminalBackend().upgrade_hint())

    assert "connectify configure iterm" in hint
    assert terminals.ITERM_DOWNLOAD_URL in hint


def test_the_iterm2_backend_explains_the_automation_permission():
    hint = " ".join(terminals.ITerm2Backend().permission_hint())

    assert "Automation" in hint


def test_only_the_terminal_backend_offers_an_upgrade():
    assert terminals.ITerm2Backend().upgrade_hint() == []


# --- app detection -----------------------------------------------------------

def test_terminal_is_looked_for_where_macos_actually_keeps_it(monkeypatch, tmp_path):
    """Terminal.app lives on the system volume, not in /Applications."""
    utilities = tmp_path / "System" / "Applications" / "Utilities"
    utilities.mkdir(parents=True)
    (utilities / "Terminal.app").mkdir()

    monkeypatch.setattr(iterm_profiles, "_applescript_app_path", lambda bundle_id: None)
    monkeypatch.setattr(terminals, "APPLE_TERMINAL_SEARCH_PATHS", [str(utilities)])

    assert terminals.AppleTerminalBackend().find() == str(utilities / "Terminal.app")
