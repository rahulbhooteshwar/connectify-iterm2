"""Starting the web UI at login."""

import os
import plistlib
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import autostart


@pytest.fixture
def agent(tmp_path, monkeypatch):
    """A LaunchAgents folder of our own, and a launchctl that says yes."""
    plist = tmp_path / "LaunchAgents" / f"{autostart.LABEL}.plist"
    monkeypatch.setattr(autostart, 'PLIST_PATH', plist)
    monkeypatch.setattr(autostart, 'connectify_binary', lambda: str(tmp_path / "connectify"))
    (tmp_path / "connectify").write_text("#!/bin/sh\n")

    calls = []

    class Result:
        returncode = 0
        stdout = ''
        stderr = ''

    def fake_launchctl(*args, **kwargs):
        calls.append(args)
        return Result()

    monkeypatch.setattr(autostart, '_launchctl', fake_launchctl)
    monkeypatch.setattr(sys, 'platform', 'darwin')
    return plist, calls


def test_enable_writes_a_plist_launchd_can_read(agent):
    plist, calls = agent

    ok, message = autostart.enable()

    assert ok, message
    assert plist.exists()

    with open(plist, 'rb') as f:
        contents = plistlib.load(f)

    assert contents['Label'] == autostart.LABEL
    # The server itself, in the foreground. `ui start` would spawn it and
    # exit, and launchd would then restart the launcher on a timer for ever -
    # which is both wrong and the shape endpoint security tools flag.
    assert contents['ProgramArguments'][1:] == ['--silent']
    assert contents['KeepAlive'] is False, "nothing should respawn behind the user's back"
    assert os.path.isabs(contents['ProgramArguments'][0]), \
        "launchd expands neither ~ nor $HOME"
    assert contents['RunAtLoad'] is True

    assert any('bootstrap' in call for call in calls), "the agent is loaded, not just written"


def test_enable_replaces_an_existing_registration(agent):
    """Re-running it has to repair, not fail on 'already loaded'."""
    plist, calls = agent
    autostart.enable()
    calls.clear()

    ok, _ = autostart.enable()

    assert ok
    assert any('bootout' in call for call in calls), "the old registration is removed first"


def test_disable_removes_it(agent):
    plist, _ = agent
    autostart.enable()

    ok, message = autostart.disable()

    assert ok, message
    assert not plist.exists()


def test_disable_on_a_machine_that_never_had_it(agent):
    ok, message = autostart.disable()
    assert ok
    assert 'not set up' in message


def test_status_spots_an_agent_pointing_at_a_binary_that_moved(agent, tmp_path):
    """A reinstall elsewhere leaves launchd running something that is gone."""
    plist, _ = agent
    autostart.enable()
    (tmp_path / "connectify").unlink()

    state = autostart.status()

    assert state['configured']
    assert state['stale']
    assert 'no longer exists' in autostart.describe(state)


def test_status_when_nothing_is_configured(agent):
    state = autostart.status()

    assert not state['configured']
    assert not state['loaded']
    assert 'not set up' in autostart.describe(state)


def test_enable_needs_the_command_to_exist(agent, monkeypatch):
    monkeypatch.setattr(autostart, 'connectify_binary', lambda: None)

    ok, message = autostart.enable()

    assert not ok
    assert 'Could not find' in message


def test_it_is_macos_only(agent, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')

    ok, message = autostart.enable()

    assert not ok
    assert 'macOS' in message
    assert 'not applicable' in autostart.describe()


# --- the shell-profile alternative -------------------------------------------
#
# A LaunchAgent is persistence, and endpoint security watches persistence. On a
# managed Mac the way through is often to not persist at all: start the server
# from the shell profile instead, so there is no login hook to flag.

@pytest.fixture
def rc(tmp_path, monkeypatch):
    profile = tmp_path / ".zshrc"
    monkeypatch.setenv('SHELL', '/bin/zsh')
    monkeypatch.setattr(autostart, 'shell_profile', lambda: profile)
    return profile


ORIGINAL_RC = 'export PATH=/usr/local/bin:$PATH\nalias ll="ls -la"\n'


def test_enable_shell_adds_a_marked_block(rc):
    rc.write_text(ORIGINAL_RC)

    ok, message = autostart.enable_shell()

    assert ok, message
    text = rc.read_text()
    assert autostart.BEGIN_MARK in text and autostart.END_MARK in text
    assert 'connectify ui start' in text
    assert ORIGINAL_RC in text, "what was already there is left alone"
    # Backgrounded: `ui start` waits for the server, and a terminal should not
    assert '&)' in text or '&\n' in text


def test_enabling_twice_does_not_stack_up(rc):
    rc.write_text(ORIGINAL_RC)

    autostart.enable_shell()
    first = rc.read_text()
    autostart.enable_shell()

    assert rc.read_text().count(autostart.BEGIN_MARK) == 1
    assert rc.read_text() == first


def test_disable_shell_puts_the_file_back(rc):
    rc.write_text(ORIGINAL_RC)
    autostart.enable_shell()

    ok, message = autostart.disable_shell()

    assert ok, message
    assert rc.read_text() == ORIGINAL_RC, "byte for byte, including the trailing newline"


def test_disable_shell_when_it_was_never_enabled(rc):
    rc.write_text(ORIGINAL_RC)

    ok, message = autostart.disable_shell()

    assert ok
    assert rc.read_text() == ORIGINAL_RC


def test_enable_shell_creates_the_file_if_there_is_none(rc):
    assert not rc.exists()

    ok, _ = autostart.enable_shell()

    assert ok and rc.exists()
    assert autostart.BEGIN_MARK in rc.read_text()


def test_status_reports_the_shell_route(rc):
    rc.write_text(ORIGINAL_RC)
    autostart.enable_shell()

    assert autostart.shell_status()['configured'] is True
    assert str(rc) in autostart.shell_status()['profile']


def test_fish_gets_fish_syntax(tmp_path, monkeypatch):
    profile = tmp_path / "config.fish"
    monkeypatch.setenv('SHELL', '/opt/homebrew/bin/fish')
    monkeypatch.setattr(autostart, 'shell_profile', lambda: profile)

    autostart.enable_shell()
    text = profile.read_text()

    assert 'if command -v connectify' in text and text.count('end') >= 1
    assert '&&' not in text, "fish does not take &&"


def test_an_unfamiliar_shell_says_what_to_add_by_hand(monkeypatch):
    monkeypatch.setenv('SHELL', '/usr/bin/ksh')

    ok, message = autostart.enable_shell()

    assert not ok
    assert 'connectify ui start' in message, "tell them the line rather than just failing"
