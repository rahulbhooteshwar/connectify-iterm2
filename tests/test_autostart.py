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
