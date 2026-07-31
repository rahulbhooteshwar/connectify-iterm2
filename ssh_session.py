#!/usr/bin/env python3
"""
Launching SSH sessions without leaking secrets.

The old approach wrote the password to a file in $HOME and typed
``sshpass -f <file> ssh ...`` into an interactive shell. That needed the
third-party sshpass binary, put the password on disk, and left the whole
command in the terminal scrollback and the shell's history.

This module does it differently:

* **No sshpass.** OpenSSH asks a helper program for the password when
  ``SSH_ASKPASS`` is set and ``SSH_ASKPASS_REQUIRE=force`` (OpenSSH 8.4+, i.e.
  every macOS since Monterey). That same mechanism supplies SSH key
  passphrases, so encrypted keys work too.
* **No secret on disk.** The helper reads the secret from a FIFO in a private
  0700 directory. A FIFO stores nothing - the bytes pass through kernel memory
  from this process straight into ssh. It is served a limited number of times,
  for a limited window, then removed.
* **Nothing typed into a shell.** iTerm2 runs the launcher script directly as
  the session's command, so the tab contains the SSH session and nothing else:
  no command line in the scrollback, no entry in the shell history.

Nothing written to disk here is secret: the launcher and the askpass helper
only ever reference the FIFO's path.
"""

import errno
import os
import shutil
import stat
import subprocess
import secrets
import threading
import time
from pathlib import Path

# The secret is offered a few times so ssh's own retries work, but not forever
DEFAULT_MAX_READS = 3
DEFAULT_TIMEOUT = 180

# Belt-and-braces removal of a session directory the launcher didn't clean up
RUNTIME_SWEEP_AGE = 6 * 60 * 60


def runtime_root():
    """Private directory for session scratch files.

    Kept free of spaces so the path can be handed to iTerm2 as a command
    without quoting games; falls back to /tmp if the home directory has one.
    """
    home_root = Path.home() / '.connectify' / 'run'
    if ' ' not in str(home_root):
        return home_root
    return Path(f"/tmp/connectify-run-{os.getuid()}")


def sweep_runtime_dir(max_age=RUNTIME_SWEEP_AGE):
    """Remove leftover session directories from crashed or killed sessions."""
    root = runtime_root()
    if not root.is_dir():
        return 0

    removed = 0
    cutoff = time.time() - max_age
    for entry in root.iterdir():
        try:
            if entry.is_dir() and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


class SecretChannel:
    """A one-shot FIFO that hands a secret to ssh's askpass helper.

    The secret never touches the filesystem: a FIFO is a rendezvous point, and
    the bytes only exist in this process and in ssh's memory.
    """

    def __init__(self, directory, secret, max_reads=DEFAULT_MAX_READS, timeout=DEFAULT_TIMEOUT):
        self.path = Path(directory) / 'askpass.fifo'
        self.secret = secret
        self.max_reads = max_reads
        self.timeout = timeout
        self.served = 0
        self._thread = None
        self._stop = threading.Event()

        os.mkfifo(self.path, 0o600)

    def start(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        try:
            self.path.unlink()
        except OSError:
            pass

    def _serve(self):
        """Write the secret to whoever opens the FIFO, then get out of the way.

        Opening a FIFO write-only with O_NONBLOCK fails with ENXIO until a
        reader shows up, which makes it a clean way to wait for ssh without
        blocking forever if ssh never asks (key auth, cancelled session...).

        After each hand-off the FIFO is replaced with a fresh one. Re-arming the
        same FIFO would let a reader that is still draining pick up a second
        copy of the secret, since a new writer keeps it from seeing EOF.
        """
        payload = (self.secret or '').encode('utf-8') + b'\n'
        deadline = time.time() + self.timeout

        while self.served < self.max_reads and not self._stop.is_set():
            if time.time() > deadline:
                break

            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as e:
                if e.errno == errno.ENXIO:      # nobody reading yet
                    time.sleep(0.05)
                    continue
                break                            # gone, or something worse

            try:
                with os.fdopen(fd, 'wb') as fifo:
                    fifo.write(payload)
                self.served += 1
            except OSError:
                # ssh closed the pipe without reading - nothing to do about it
                pass

            if self.served < self.max_reads and not self._rearm():
                break

        self.stop()

    def _rearm(self):
        """Swap in a fresh FIFO so the next prompt gets exactly one answer."""
        try:
            self.path.unlink()
            os.mkfifo(self.path, 0o600)
            return True
        except OSError:
            return False


class SSHSession:
    """Everything needed to start one session, and the means to clean it up."""

    def __init__(self, directory, launcher, channel=None):
        self.directory = Path(directory)
        self.launcher = Path(launcher)
        self.channel = channel

    @property
    def command(self):
        """What iTerm2 should run as the session's command."""
        return str(self.launcher)

    def cleanup(self):
        if self.channel:
            self.channel.stop()
        shutil.rmtree(self.directory, ignore_errors=True)


def build_ssh_argv(host, credential=None, ssh_options=None):
    """The ssh command line for a host - never contains a secret."""
    credential = credential or {}
    argv = ['ssh']

    port = host.get('port', 22)
    if port and int(port) != 22:
        argv += ['-p', str(port)]

    for option in (ssh_options or []):
        argv += ['-o', str(option)]

    if credential.get('type') == 'key':
        key_path = credential.get('ssh_key_path') or host.get('ssh_key_path')
        if key_path:
            argv += ['-i', str(Path(key_path).expanduser())]

    argv.append(f"{host['username']}@{host['hostname']}")
    return argv


def _shell_quote(value):
    return "'" + str(value).replace("'", "'\\''") + "'"


def _write_script(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.chmod(path, stat.S_IRWXU)


def secret_for(credential):
    """The secret ssh will ask for, if any.

    A password credential answers the password prompt; a key credential with a
    passphrase answers the passphrase prompt. Both arrive through the same
    askpass mechanism.
    """
    credential = credential or {}
    if credential.get('type') == 'password':
        return credential.get('password') or ''
    if credential.get('type') == 'key':
        return credential.get('passphrase') or ''
    return ''


def prepare_session(host, credential=None, ssh_options=None, keep_shell=True,
                    timeout=DEFAULT_TIMEOUT):
    """Create the scratch directory, scripts and secret channel for a session.

    Returns an :class:`SSHSession`. The caller launches ``session.command`` in
    iTerm2 and calls ``session.cleanup()`` if the launch fails.
    """
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, stat.S_IRWXU)

    directory = root / secrets.token_hex(8)
    directory.mkdir(mode=0o700)

    argv = build_ssh_argv(host, credential, ssh_options)
    ssh_command = ' '.join(_shell_quote(part) for part in argv)

    secret = secret_for(credential)
    channel = None
    askpass_setup = ''

    if secret:
        channel = SecretChannel(directory, secret, timeout=timeout)
        askpass_path = directory / 'askpass.sh'

        # The helper holds no secret - just the path of the FIFO to read from
        _write_script(askpass_path, (
            "#!/bin/sh\n"
            "# Connectify askpass helper: reads one secret from a private FIFO.\n"
            f"fifo={_shell_quote(channel.path)}\n"
            "n=0\n"
            "while [ $n -lt 100 ]; do\n"
            "  [ -p \"$fifo\" ] && exec /bin/cat \"$fifo\"\n"
            "  n=$((n+1))\n"
            "  sleep 0.1\n"
            "done\n"
            "exit 1\n"
        ))

        askpass_setup = (
            f"SSH_ASKPASS={_shell_quote(askpass_path)}\n"
            "SSH_ASKPASS_REQUIRE=force\n"
            # Pre-8.4 OpenSSH only consults SSH_ASKPASS when DISPLAY is set
            "DISPLAY=${DISPLAY:-:0}\n"
            "export SSH_ASKPASS SSH_ASKPASS_REQUIRE DISPLAY\n"
        )

    # iTerm2 runs this instead of a login shell, so nothing lands in the shell
    # history and the command is never echoed into the tab.
    tail = (
        'if [ "$status" -ne 0 ]; then\n'
        '  printf "\\n[connectify] ssh exited with status %s\\n" "$status"\n'
        'fi\n'
        'exec "${SHELL:-/bin/sh}" -l\n'
    ) if keep_shell else 'exit "$status"\n'

    launcher_path = directory / 'session.sh'
    _write_script(launcher_path, (
        "#!/bin/sh\n"
        "# Connectify session launcher - contains no secrets.\n"
        f"{askpass_setup}"
        f"{ssh_command}\n"
        "status=$?\n"
        f"rm -rf {_shell_quote(directory)}\n"
        f"{tail}"
    ))

    if channel:
        channel.start()

    return SSHSession(directory, launcher_path, channel)
