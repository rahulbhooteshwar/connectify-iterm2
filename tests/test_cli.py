"""The CLI is deliberately small - hosts live in the web UI.

These tests lock that surface down so the interactive commands don't creep back.
"""

import json
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
    'configure iterm', 'configure terminal',
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


def test_doctor_says_which_terminal_sessions_open_in(tmp_path):
    """Everything needed to answer 'what happens when I hit connect?'."""
    result = run_cli('doctor', home=tmp_path)

    assert 'Terminal' in result.stdout
    assert 'Sessions open in' in result.stdout
    # Without iTerm2: what is missing, and the one command that fixes it
    assert 'not imported' in result.stdout
    assert 'connectify configure iterm' in result.stdout


# --- choosing a terminal -----------------------------------------------------

def test_configure_status_names_the_terminal_and_its_permission(tmp_path):
    result = run_cli('configure', home=tmp_path)

    assert result.returncode == 0
    assert 'macOS Terminal' in result.stdout
    assert 'Accessibility' in result.stdout


def test_configure_iterm_without_iterm2_changes_nothing(tmp_path):
    """The follow-up command has to be honest when there is still no iTerm2."""
    result = run_cli('configure', 'iterm', home=tmp_path)

    assert result.returncode == 1
    assert 'iTerm2 is not installed' in result.stdout
    assert 'nothing is broken' in result.stdout

    config = tmp_path / '.connectify' / 'hosts.json'
    if config.exists():
        assert 'terminal' not in json.loads(config.read_text())

    profiles_dir = tmp_path / 'Library' / 'Application Support' / 'iTerm2'
    assert not profiles_dir.exists(), "no iTerm2 folder may be created for a missing app"


def test_configure_terminal_persists_the_preference(tmp_path):
    result = run_cli('configure', 'terminal', home=tmp_path)

    assert result.returncode == 0
    config = json.loads((tmp_path / '.connectify' / 'hosts.json').read_text())
    assert config['terminal'] == 'terminal'


def test_profiles_install_without_iterm2_points_at_configure(tmp_path):
    result = run_cli('profiles', 'install', home=tmp_path)

    assert result.returncode == 1
    assert 'connectify configure iterm' in result.stdout


def test_the_installer_no_longer_blocks_on_a_missing_iterm2(monkeypatch, capsys):
    """The whole point of the change: no iTerm2 must not stop an install."""
    import installer
    import iterm_profiles

    monkeypatch.setattr(installer.sys, "platform", "darwin")
    monkeypatch.setattr(installer.os, "geteuid", lambda: 501)
    monkeypatch.setattr(iterm_profiles, "find_iterm2", lambda: None)

    assert installer.check_requirements() is True

    output = capsys.readouterr().out
    assert "macOS Terminal" in output
    assert "connectify configure iterm" in output


def test_the_installer_skips_the_profile_import_without_iterm2(monkeypatch, capsys):
    import installer
    import iterm_profiles

    monkeypatch.setattr(iterm_profiles, "find_iterm2", lambda: None)
    monkeypatch.setattr(iterm_profiles, "install_bundled_profiles", lambda **kw: pytest.fail(
        "profiles must not be imported when iTerm2 is absent"))

    installer.install_profiles()

    assert "Skipped" in capsys.readouterr().out


@pytest.mark.parametrize("removed", [
    'add_host', 'list_hosts', 'display_host_menu', 'display_simple_host_menu',
    'filter_hosts_internal', 'prompt_for_group', 'prompt_for_iterm_profile',
])
def test_interactive_manager_methods_are_gone(removed):
    assert not hasattr(main_module.SSHManager, removed)


def test_manager_keeps_what_the_web_ui_needs():
    for kept in ['launch_session', 'launch_iterm_session', 'filter_hosts', 'get_host',
                 'add_host_programmatic',
                 'update_host', 'delete_host', 'hosts_using_credential',
                 'rename_credential_references', 'clean_legacy_host_fields']:
        assert hasattr(main_module.SSHManager, kept), f"{kept} is still used by the API"


def test_no_interactive_prompt_dependency():
    """inquirer/readchar/blessed were only needed by the terminal UI."""
    assert 'inquirer' not in sys.modules
    with open(os.path.join(REPO_ROOT, 'pyproject.toml')) as f:
        assert 'inquirer' not in f.read()


# --- installer ---------------------------------------------------------------

def test_installer_ui_is_bundled_not_a_host_dependency():
    """install.sh must not need rich (or python) on the user's machine."""
    import installer

    # The pretty parts live in the binary
    for attr in ('run_install', 'run_upgrade', 'download_release', 'check_requirements'):
        assert hasattr(installer, attr)

    with open(os.path.join(REPO_ROOT, 'install.sh')) as f:
        bootstrap = f.read()

    assert 'rich' not in bootstrap
    assert '/connectify" install' in bootstrap, "the script hands off to the bundled installer"
    assert '--version' in bootstrap, "the version being installed is passed through"
    # The heavy lifting is no longer duplicated in bash
    for gone in ('install_binary()', 'setup_path()', 'check_and_install_sshpass'):
        assert gone not in bootstrap


def test_the_bootstrap_draws_its_own_progress_bar():
    """curl's --progress-bar is a row of '#'; the download deserves better."""
    with open(os.path.join(REPO_ROOT, 'install.sh')) as f:
        bootstrap = f.read()

    # Ignore comments - one of them names the flag it replaced
    code = '\n'.join(l for l in bootstrap.splitlines() if not l.lstrip().startswith('#'))
    assert '--progress-bar' not in code

    assert 'draw_bar()' in bootstrap

    # The bar is drawn from inside download(), whose stdout the caller
    # captures with $( ). Testing fd 1 for a terminal is therefore always
    # false and the bar silently never appears - it has to test fd 2.
    body = bootstrap[bootstrap.index('download() {'):bootstrap.index('\nmain() {')]
    assert '-t 1' not in body, "stdout is captured here; the terminal test must be on fd 2"
    assert body.count('-t 2') == 2
    assert '━' in bootstrap and '─' in bootstrap, "filled and empty read apart without colour"
    # BSD awk (what macOS ships) has no IGNORECASE
    assert 'IGNORECASE' not in code


def test_autostart_is_a_command_not_a_hosted_script():
    """It used to be a curl|bash script; the old URL now forwards to this."""
    result = run_cli('--help')
    assert 'connectify autostart' in result.stdout

    status = run_cli('autostart')
    assert status.returncode == 0
    assert 'Auto-start' in status.stdout

    with open(os.path.join(REPO_ROOT, 'setup-autostart.sh')) as f:
        script = f.read()
    assert 'connectify autostart' in script, "the old script forwards to the command"
    assert 'launchctl load' not in script, "and no longer has its own copy of the logic"


def test_the_doctor_reports_autostart():
    result = run_cli('doctor')
    assert 'Auto-start' in result.stdout


def test_install_and_upgrade_are_documented_commands():
    result = run_cli('--help')
    assert 'connectify upgrade' in result.stdout


def test_install_requires_a_source_directory():
    result = run_cli('install')
    assert result.returncode == 1
    assert '--from' in result.stdout


def test_tasks_replace_the_makefile():
    assert not os.path.exists(os.path.join(REPO_ROOT, 'Makefile')), "the Makefile is gone"

    result = subprocess.run([sys.executable, os.path.join(REPO_ROOT, 'tasks.py')],
                            capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)
    assert result.returncode == 0
    for task_name in ('setup', 'ui', 'test', 'build', 'install', 'release', 'clean'):
        assert task_name in result.stdout
