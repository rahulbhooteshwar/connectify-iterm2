"""Launching a session must not leak the secret anywhere.

These exercise the real mechanism: a FIFO, an askpass helper and a launcher
script. Where OpenSSH is available they also check that ssh itself accepts the
handoff.
"""

import os
import shutil
import subprocess
import sys
import time

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ssh_session

SECRET = "correct-horse-battery-staple"

HOST = {
    "name": "prod-web",
    "hostname": "web.example.com",
    "username": "admin",
    "port": 2222,
}
PASSWORD_CREDENTIAL = {"name": "pw", "type": "password", "password": SECRET}
KEY_CREDENTIAL = {"name": "k", "type": "key", "ssh_key_path": "~/.ssh/id_ed25519",
                  "passphrase": SECRET}


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    root = tmp_path / "run"
    monkeypatch.setattr(ssh_session, "runtime_root", lambda: root)
    return root


# --- the command line --------------------------------------------------------

def test_ssh_argv_never_carries_a_secret():
    argv = ssh_session.build_ssh_argv(HOST, PASSWORD_CREDENTIAL,
                                      ["StrictHostKeyChecking=no"])

    assert argv == ['ssh', '-p', '2222', '-o', 'StrictHostKeyChecking=no',
                    'admin@web.example.com']
    assert SECRET not in ' '.join(argv)
    assert 'sshpass' not in ' '.join(argv)


def test_default_port_is_left_implicit():
    argv = ssh_session.build_ssh_argv({**HOST, "port": 22})
    assert '-p' not in argv


def test_key_credential_adds_the_identity_file(tmp_path):
    key = tmp_path / "id_ed25519"
    argv = ssh_session.build_ssh_argv(HOST, {**KEY_CREDENTIAL, "ssh_key_path": str(key)})

    assert '-i' in argv and str(key) in argv


@pytest.mark.parametrize("host_username,credential_username,expected", [
    ("admin", "ubuntu", "ubuntu"),   # the credential's login wins
    ("admin", "", "admin"),          # ... and the host's is the fallback
    ("", "ubuntu", "ubuntu"),        # a host can leave it to the credential
    ("  ", "  ubuntu  ", "ubuntu"),  # whitespace is not a username
    ("", "", ""),                    # neither: ssh would use the local account
])
def test_effective_username(host_username, credential_username, expected):
    host = {**HOST, "username": host_username}
    credential = {**PASSWORD_CREDENTIAL, "username": credential_username}

    assert ssh_session.effective_username(host, credential) == expected


def test_the_credentials_username_is_what_ssh_is_given():
    argv = ssh_session.build_ssh_argv(HOST, {**PASSWORD_CREDENTIAL, "username": "ubuntu"})
    assert argv[-1] == "ubuntu@web.example.com"

    # And a host with no username of its own still gets one
    argv = ssh_session.build_ssh_argv({**HOST, "username": ""},
                                      {**PASSWORD_CREDENTIAL, "username": "ubuntu"})
    assert argv[-1] == "ubuntu@web.example.com"


def test_no_username_anywhere_leaves_ssh_to_its_own_default():
    argv = ssh_session.build_ssh_argv({**HOST, "username": ""}, PASSWORD_CREDENTIAL)
    assert argv[-1] == "web.example.com"


@pytest.mark.parametrize("credential,expected", [
    (PASSWORD_CREDENTIAL, SECRET),
    (KEY_CREDENTIAL, SECRET),
    ({"type": "key", "ssh_key_path": "~/.ssh/id_rsa"}, ''),
    ({"type": "password", "password": ""}, ''),
    (None, ''),
])
def test_secret_for(credential, expected):
    """Passwords and key passphrases both go through the same channel."""
    assert ssh_session.secret_for(credential) == expected


# --- what lands on disk ------------------------------------------------------

def test_no_file_written_for_a_session_contains_the_secret(runtime):
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL)
    try:
        files = [p for p in session.directory.iterdir() if p.is_file()]
        assert files, "the launcher and askpass helper should exist"

        for path in files:
            assert SECRET not in path.read_text(), f"{path.name} leaks the secret"

        launcher = session.launcher.read_text()
        assert 'sshpass' not in launcher
        assert 'SSH_ASKPASS_REQUIRE=force' in launcher
        assert 'ssh' in launcher
    finally:
        session.cleanup()


def test_session_files_are_private(runtime):
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL)
    try:
        assert oct(session.directory.stat().st_mode & 0o777) == '0o700'
        assert oct(session.launcher.stat().st_mode & 0o777) == '0o700'
        # The FIFO is a rendezvous point, not storage
        fifo = session.channel.path
        assert fifo.is_fifo()
        assert oct(fifo.stat().st_mode & 0o777) == '0o600'
    finally:
        session.cleanup()


def test_no_channel_when_there_is_no_secret(runtime):
    session = ssh_session.prepare_session(HOST, {"type": "key", "ssh_key_path": "~/.ssh/id_rsa"})
    try:
        assert session.channel is None
        assert 'SSH_ASKPASS' not in session.launcher.read_text()
    finally:
        session.cleanup()


def test_cleanup_removes_everything(runtime):
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL)
    directory = session.directory

    session.cleanup()

    assert not directory.exists()


# --- handing the secret over -------------------------------------------------

def test_askpass_helper_delivers_the_secret(runtime):
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL)
    try:
        askpass = session.directory / 'askpass.sh'
        result = subprocess.run([str(askpass)], capture_output=True, text=True, timeout=30)

        assert result.stdout.strip() == SECRET
        assert session.channel.served == 1
    finally:
        session.cleanup()


def test_the_secret_is_served_a_limited_number_of_times(runtime):
    """ssh may retry, but the channel must not be an unlimited oracle."""
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL)
    try:
        askpass = str(session.directory / 'askpass.sh')
        for _ in range(ssh_session.DEFAULT_MAX_READS):
            assert subprocess.run([askpass], capture_output=True, text=True,
                                  timeout=30).stdout.strip() == SECRET

        assert session.channel.served == ssh_session.DEFAULT_MAX_READS
        # The FIFO is gone once it has done its job
        deadline = time.time() + 5
        while session.channel.path.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert not session.channel.path.exists()
    finally:
        session.cleanup()


def test_the_channel_gives_up_if_ssh_never_asks(runtime):
    """Key auth can succeed without a prompt - don't wait around forever."""
    session = ssh_session.prepare_session(HOST, PASSWORD_CREDENTIAL, timeout=0.2)
    try:
        deadline = time.time() + 5
        while session.channel.path.exists() and time.time() < deadline:
            time.sleep(0.05)

        assert not session.channel.path.exists()
        assert session.channel.served == 0
    finally:
        session.cleanup()


# --- housekeeping ------------------------------------------------------------

def test_sweep_removes_stale_session_directories(runtime):
    runtime.mkdir(parents=True)
    stale = runtime / "stale"
    stale.mkdir()
    os.utime(stale, (time.time() - 10 * 60 * 60, time.time() - 10 * 60 * 60))
    fresh = runtime / "fresh"
    fresh.mkdir()

    removed = ssh_session.sweep_runtime_dir()

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()


def test_runtime_root_avoids_paths_with_spaces(monkeypatch, tmp_path):
    """iTerm2 gets this path as a command, so spaces would break the launch."""
    spaced = tmp_path / "Some User"
    monkeypatch.setattr(ssh_session.Path, "home", classmethod(lambda cls: spaced))

    assert ' ' not in str(ssh_session.runtime_root())


# --- against real OpenSSH ----------------------------------------------------

@pytest.mark.skipif(not shutil.which('ssh-keygen'), reason="OpenSSH not installed")
def test_openssh_accepts_the_passphrase_from_our_helper(runtime, tmp_path):
    """The same mechanism unlocks an encrypted SSH key - previously unsupported."""
    key = tmp_path / "id_ed25519"
    subprocess.run(['ssh-keygen', '-t', 'ed25519', '-N', SECRET, '-f', str(key), '-q'],
                   check=True, timeout=60)

    session = ssh_session.prepare_session(
        HOST, {"type": "key", "ssh_key_path": str(key), "passphrase": SECRET})
    try:
        env = {
            **os.environ,
            'SSH_ASKPASS': str(session.directory / 'askpass.sh'),
            'SSH_ASKPASS_REQUIRE': 'force',
            'DISPLAY': ':0',
        }
        result = subprocess.run(['ssh-keygen', '-y', '-f', str(key)],
                                capture_output=True, text=True, env=env,
                                stdin=subprocess.DEVNULL, timeout=60)

        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith('ssh-ed25519')
    finally:
        session.cleanup()


# --- the iTerm2 hand-off -----------------------------------------------------

def test_launch_passes_a_command_to_iterm_and_never_types_the_secret(runtime, tmp_path, monkeypatch):
    """The old implementation typed `sshpass -f <file> ssh ...` into a shell."""
    import main

    config = tmp_path / "hosts.json"
    config.write_text('{"hosts": []}')
    manager = main.SSHManager(str(config))
    monkeypatch.setattr(manager, "_ensure_iterm_running", lambda: True)

    scripts = []

    def fake_run(argv, **kwargs):
        scripts.append(argv[-1])
        # iTerm2 answers with the new session's id
        return subprocess.CompletedProcess(argv, 0, 'w0t1p0:9C1D-session-id', '')

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    host = {**HOST, "iterm_profile": "connectify-PROD",
            "ssh_options": ["StrictHostKeyChecking=no"]}
    assert manager.launch_iterm_session(host, PASSWORD_CREDENTIAL) is True

    applescript = scripts[0]
    assert SECRET not in applescript, "the secret must never reach AppleScript"
    assert 'write text' not in applescript, "nothing may be typed into a shell"
    assert 'sshpass' not in applescript
    assert 'command "' in applescript, "the session runs the launcher directly"
    assert 'connectify-PROD' in applescript

    # The launcher it points at runs the expected ssh command
    launcher = applescript.split('command "')[1].split('"')[0]
    body = open(launcher).read()
    assert "'admin@web.example.com'" in body
    assert "'-o' 'StrictHostKeyChecking=no'" in body
    assert SECRET not in body

    shutil.rmtree(os.path.dirname(launcher), ignore_errors=True)


def test_launch_fails_loudly_when_iterm_does_not_confirm_the_tab(runtime, tmp_path, monkeypatch):
    """A silent AppleScript used to look like success; now it's an error."""
    import main

    config = tmp_path / "hosts.json"
    config.write_text('{"hosts": []}')
    manager = main.SSHManager(str(config))
    monkeypatch.setattr(manager, "_ensure_iterm_running", lambda: True)
    monkeypatch.setattr(main.SSHManager, "LAUNCH_SETTLE_SECONDS", 0)

    # No session id back = iTerm2 never opened anything
    monkeypatch.setattr(main.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, '', ''))

    with pytest.raises(RuntimeError, match="Could not open a session"):
        manager.launch_iterm_session({**HOST, "iterm_profile": "Default"}, PASSWORD_CREDENTIAL)


def test_launch_retries_a_transient_applescript_error(runtime, tmp_path, monkeypatch):
    """iTerm2 busy mid-launch shouldn't lose the session."""
    import main

    config = tmp_path / "hosts.json"
    config.write_text('{"hosts": []}')
    manager = main.SSHManager(str(config))
    monkeypatch.setattr(manager, "_ensure_iterm_running", lambda: True)
    monkeypatch.setattr(main.SSHManager, "LAUNCH_SETTLE_SECONDS", 0)

    calls = []

    def flaky(argv, **kwargs):
        calls.append(argv)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(
                1, argv, stderr="iTerm got an error: Can't get current window")
        return subprocess.CompletedProcess(argv, 0, 'session-id', '')

    monkeypatch.setattr(main.subprocess, "run", flaky)

    assert manager.launch_iterm_session({**HOST, "iterm_profile": "Default"},
                                        PASSWORD_CREDENTIAL) is True
    assert len(calls) == 2, "the transient failure should have been retried"


def test_a_failed_launch_cleans_up_its_session_directory(runtime, tmp_path, monkeypatch):
    import main

    config = tmp_path / "hosts.json"
    config.write_text('{"hosts": []}')
    manager = main.SSHManager(str(config))
    monkeypatch.setattr(manager, "_ensure_iterm_running", lambda: False)
    monkeypatch.setattr(main.SSHManager, "LAUNCH_SETTLE_SECONDS", 0)

    with pytest.raises(RuntimeError):
        manager.launch_iterm_session(HOST, PASSWORD_CREDENTIAL)

    # No launcher, askpass helper or FIFO left behind
    assert list(runtime.iterdir()) == []


def test_rapid_launches_are_serialized_and_spaced(runtime, tmp_path, monkeypatch):
    """Firing several connects at once must not have them race in iTerm2."""
    import threading
    import main

    config = tmp_path / "hosts.json"
    config.write_text('{"hosts": []}')
    manager = main.SSHManager(str(config))
    monkeypatch.setattr(manager, "_ensure_iterm_running", lambda: True)
    monkeypatch.setattr(main.SSHManager, "LAUNCH_SETTLE_SECONDS", 0.05)
    monkeypatch.setattr(main.SSHManager, "_last_launch_at", 0.0)

    overlaps = []
    in_flight = []
    lock = threading.Lock()

    def watch(argv, **kwargs):
        with lock:
            in_flight.append(1)
            overlaps.append(len(in_flight))
        time.sleep(0.02)
        with lock:
            in_flight.pop()
        return subprocess.CompletedProcess(argv, 0, 'session-id', '')

    monkeypatch.setattr(main.subprocess, "run", watch)

    threads = [threading.Thread(
        target=manager.launch_iterm_session,
        args=({**HOST, "name": f"host-{i}", "iterm_profile": "Default"}, PASSWORD_CREDENTIAL))
        for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert max(overlaps) == 1, "iTerm2 was scripted by two launches at once"
    assert len(overlaps) == 5
