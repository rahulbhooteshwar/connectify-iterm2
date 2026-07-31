"""The CLI is deliberately small - hosts live in the web UI.

These tests lock that surface down so the interactive commands don't creep back.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO_ROOT)

import main as main_module


def run_cli(*args, home=None):
    env = dict(os.environ)
    if home:
        env['HOME'] = str(home)
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, 'connectify.py'), *args],
        capture_output=True, text=True, timeout=120, env=env, cwd=REPO_ROOT,
    )


SUPPORTED = [
    'ui start', 'ui stop', 'ui restart', 'ui status', 'ui logs',
    'profiles list', 'profiles install',
    'doctor', 'version',
]

REMOVED = ['--add', '--list', '--simple', '--debug', 'Interactive host selection']


def test_help_documents_only_the_supported_commands():
    result = run_cli('--help')

    assert result.returncode == 0
    for command in SUPPORTED:
        assert command in result.stdout, f"'{command}' missing from help"
    for command in REMOVED:
        assert command not in result.stdout, f"'{command}' should be gone"


def test_no_arguments_shows_help_instead_of_a_host_picker():
    result = run_cli()

    assert result.returncode == 0
    assert 'connectify ui start' in result.stdout


def test_version():
    result = run_cli('version')

    assert result.returncode == 0
    assert 'Connectify v' in result.stdout


def test_removed_commands_fail_with_guidance():
    for command in ['--add', '--list', '--simple', 'connect']:
        result = run_cli(command)
        assert result.returncode == 1, f"'{command}' should not be accepted"
        assert 'Unknown command' in result.stdout
        assert 'connectify ui start' in result.stdout


def test_doctor_reports_the_essentials(tmp_path):
    result = run_cli('doctor', home=tmp_path)

    # Keychain checks fail outside macOS, so only assert on the sections
    assert 'Web UI server' in result.stdout
    assert 'iTerm2' in result.stdout
    assert 'Configuration' in result.stdout
    assert 'Credentials vault' in result.stdout


@pytest.mark.parametrize("removed", [
    'add_host', 'list_hosts', 'display_host_menu', 'display_simple_host_menu',
    'filter_hosts_internal', 'prompt_for_group', 'prompt_for_iterm_profile',
])
def test_interactive_manager_methods_are_gone(removed):
    assert not hasattr(main_module.SSHManager, removed)


def test_manager_keeps_what_the_web_ui_needs():
    for kept in ['launch_iterm_session', 'filter_hosts', 'get_host', 'add_host_programmatic',
                 'update_host', 'delete_host', 'hosts_using_credential',
                 'rename_credential_references', 'clean_legacy_host_fields']:
        assert hasattr(main_module.SSHManager, kept), f"{kept} is still used by the API"


def test_no_interactive_prompt_dependency():
    """inquirer/readchar/blessed were only needed by the terminal UI."""
    assert 'inquirer' not in sys.modules
    with open(os.path.join(REPO_ROOT, 'pyproject.toml')) as f:
        assert 'inquirer' not in f.read()
