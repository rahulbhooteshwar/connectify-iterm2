"""The connecting card a session tab shows while ssh authenticates."""

import os
import pty
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import session_splash

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_theme_colours_follow_the_tiles():
    assert session_splash.colour_for('red') != session_splash.colour_for('green')
    assert session_splash.colour_for('RED ') == session_splash.colour_for('red')
    # Anything unknown gets the neutral one rather than failing
    assert session_splash.colour_for('chartreuse') == session_splash.THEME_COLOURS['default']
    assert session_splash.colour_for(None) == session_splash.THEME_COLOURS['default']


def test_it_stops_as_soon_as_the_marker_exists(tmp_path):
    marker = tmp_path / "connected"
    marker.touch()

    started = time.time()
    assert session_splash.run(['--name', 'x', '--marker', str(marker)]) == 0
    assert time.time() - started < 2, "an already-connected session should not wait"


def test_it_gives_up_rather_than_drawing_for_ever(tmp_path):
    started = time.time()
    assert session_splash.run([
        '--name', 'x', '--marker', str(tmp_path / "never"), '--timeout', '0.3']) == 0
    assert time.time() - started < 3


def read_pty(argv, env=None):
    chunks = []

    def read(fd):
        data = os.read(fd, 4096)
        chunks.append(data)
        return data

    environment = {**os.environ, 'COLUMNS': '90', 'LINES': '24', **(env or {})}
    original = dict(os.environ)
    os.environ.update(environment)
    try:
        pty.spawn(argv, read)
    finally:
        os.environ.clear()
        os.environ.update(original)
    return b''.join(chunks).decode('utf-8', 'replace')


@pytest.mark.skipif(not os.path.exists(os.path.join(REPO_ROOT, 'connectify.py')),
                    reason="needs the CLI script")
def test_the_card_is_drawn_and_then_leaves_nothing_behind(tmp_path):
    """On a real terminal: a bordered card, erased once connected."""
    pytest.importorskip('rich')

    marker = tmp_path / "connected"
    toucher = tmp_path / "touch-later.sh"
    toucher.write_text(f"#!/bin/sh\nsleep 0.5\ntouch {marker}\n")
    toucher.chmod(0o755)

    os.spawnv(os.P_NOWAIT, '/bin/sh', ['/bin/sh', str(toucher)])

    output = read_pty([sys.executable, os.path.join(REPO_ROOT, 'connectify.py'),
                       'session-splash', '--name', 'Production DB',
                       '--target', 'ubuntu@prod.example.com:2222',
                       '--auth', 'password · prod-admin',
                       '--theme', 'red', '--marker', str(marker), '--timeout', '10'])

    assert '╭' in output and '╰' in output, "a bordered card was drawn"
    assert 'Production DB' in output
    assert 'connecting' in output

    # Transient Live erases what it drew: the tail is cursor-up + clear-line,
    # not a stranded card
    tail = output[output.rindex('╰'):]
    assert '\x1b[2K' in tail
