import json
import os
import sys
from pathlib import Path

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import iterm_profiles


REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_TERMINAL_PROFILES = ["connectify-PERSONAL", "connectify-PROD", "connectify-NONPROD"]
SHIPPED_BROWSER_PROFILES = ["connectify-UI"]
SHIPPED_PROFILES = SHIPPED_TERMINAL_PROFILES + SHIPPED_BROWSER_PROFILES


# --- shipped profile files ---------------------------------------------------

def test_shipped_profiles_exist_and_are_dynamic_profiles():
    for name in SHIPPED_PROFILES:
        path = REPO_ROOT / "profiles" / f"{name}.json"
        assert path.exists(), f"{path} is missing"

        data = json.loads(path.read_text())
        assert list(data.keys()) == ["Profiles"], "must use iTerm2's Dynamic Profile format"
        assert len(data["Profiles"]) == 1

        profile = data["Profiles"][0]
        assert profile["Name"] == name, "profile name must carry the connectify- prefix"
        assert profile["Guid"], "dynamic profiles need a Guid"


def test_shipped_profiles_have_unique_guids():
    guids = set()
    for name in SHIPPED_PROFILES:
        data = json.loads((REPO_ROOT / "profiles" / f"{name}.json").read_text())
        guids.add(data["Profiles"][0]["Guid"])
    assert len(guids) == len(SHIPPED_PROFILES)


def test_shipped_profiles_keep_their_badges():
    """Only the identifier was renamed - badges must be untouched."""
    expected_badges = {
        "connectify-PERSONAL": "PERSONAL",
        "connectify-PROD": "PRODUCTION",
        "connectify-NONPROD": "NON-PROD",
    }
    for name, badge in expected_badges.items():
        data = json.loads((REPO_ROOT / "profiles" / f"{name}.json").read_text())
        assert data["Profiles"][0]["Badge Text"] == badge


def test_shipped_browser_profile_points_at_the_connectify_ui():
    data = json.loads((REPO_ROOT / "profiles" / "connectify-UI.json").read_text())
    profile = data["Profiles"][0]

    assert profile["Custom Command"] == "Browser"
    assert profile["Initial URL"] == "http://localhost:7890/"
    assert profile["Badge Text"] == "Local", "badge untouched, only the identifier renamed"


def test_list_bundled_profiles():
    bundled = {p["name"]: p for p in iterm_profiles.list_bundled_profiles()}
    assert set(bundled) == set(SHIPPED_PROFILES)

    for name in SHIPPED_BROWSER_PROFILES:
        assert bundled[name]["is_browser"] is True
    for name in SHIPPED_TERMINAL_PROFILES:
        assert bundled[name]["is_browser"] is False


# --- installation ------------------------------------------------------------

@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def dynamic_dir(home):
    return home / "Library/Application Support/iTerm2/DynamicProfiles"


def test_install_bundled_profiles_copies_files(fake_home):
    result = iterm_profiles.install_bundled_profiles(quiet=True)

    assert result["errors"] == []
    assert sorted(result["installed"]) == sorted(f"{n}.json" for n in SHIPPED_PROFILES)

    for name in SHIPPED_PROFILES:
        installed = dynamic_dir(fake_home) / f"{name}.json"
        assert installed.exists()
        assert json.loads(installed.read_text())["Profiles"][0]["Name"] == name


def test_install_bundled_profiles_is_idempotent(fake_home):
    iterm_profiles.install_bundled_profiles(quiet=True)
    second = iterm_profiles.install_bundled_profiles(quiet=True)

    assert second["installed"] == []
    assert second["updated"] == []
    assert len(second["unchanged"]) == len(SHIPPED_PROFILES)


def test_install_bundled_profiles_repairs_modified_files(fake_home):
    iterm_profiles.install_bundled_profiles(quiet=True)
    target = dynamic_dir(fake_home) / "connectify-PROD.json"
    target.write_text('{"Profiles": []}')

    result = iterm_profiles.install_bundled_profiles(quiet=True)

    assert result["updated"] == ["connectify-PROD.json"]
    assert json.loads(target.read_text())["Profiles"][0]["Name"] == "connectify-PROD"


def test_ensure_profiles_installed_runs_once_per_version(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("CONNECTIFY_SKIP_PROFILE_INSTALL", raising=False)

    first = iterm_profiles.ensure_profiles_installed("1.2.3")
    assert first is not None and first["installed"]

    assert iterm_profiles.ensure_profiles_installed("1.2.3") is None, "marker should short-circuit"
    assert iterm_profiles.ensure_profiles_installed("1.2.4") is not None, "new version reinstalls"


def test_ensure_profiles_installed_can_be_disabled(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("CONNECTIFY_SKIP_PROFILE_INSTALL", "1")

    assert iterm_profiles.ensure_profiles_installed("1.2.3") is None
    assert not dynamic_dir(fake_home).exists()


def test_ensure_profiles_installed_skips_non_macos(fake_home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("CONNECTIFY_SKIP_PROFILE_INSTALL", raising=False)

    assert iterm_profiles.ensure_profiles_installed("1.2.3") is None


def test_ssh_manager_installs_profiles_on_startup(fake_home, monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("CONNECTIFY_SKIP_PROFILE_INSTALL", raising=False)
    monkeypatch.delenv("CONNECTIFY_TERMINAL", raising=False)

    import main
    import terminals

    # Profiles are only installed for the terminal that can read them
    monkeypatch.setattr(iterm_profiles, "find_iterm2", lambda: "/Applications/iTerm.app")
    terminals.reset_cache()

    main.SSHManager(str(fake_home / ".connectify/hosts.json"))

    for name in SHIPPED_PROFILES:
        assert (dynamic_dir(fake_home) / f"{name}.json").exists()
    assert "Installed Connectify iTerm2 profiles" in capsys.readouterr().out


def test_ssh_manager_skips_profiles_when_sessions_open_in_terminal(fake_home, monkeypatch):
    """No iTerm2 means no DynamicProfiles folder - it would be litter."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("CONNECTIFY_SKIP_PROFILE_INSTALL", raising=False)
    monkeypatch.delenv("CONNECTIFY_TERMINAL", raising=False)

    import main
    import terminals

    monkeypatch.setattr(iterm_profiles, "find_iterm2", lambda: None)
    terminals.reset_cache()

    manager = main.SSHManager(str(fake_home / ".connectify/hosts.json"))

    assert manager.terminal.key == terminals.APPLE_TERMINAL
    assert not dynamic_dir(fake_home).exists()


# --- discovery ---------------------------------------------------------------

def test_list_available_profiles_merges_sources(fake_home, monkeypatch):
    monkeypatch.setattr(iterm_profiles, "_profiles_from_preferences", lambda: [
        {"name": "Default", "guid": "abc", "source": "iterm2", "is_default": True},
        {"name": "Hotkey Window", "guid": "def", "source": "iterm2", "is_default": False},
    ])
    iterm_profiles.install_bundled_profiles(quiet=True)

    profiles = iterm_profiles.list_available_profiles(extra_names=["Legacy Profile", "Default"])
    names = [p["name"] for p in profiles]

    assert names == sorted(names, key=str.lower), "profiles are sorted by name"
    assert "Default" in names and "Hotkey Window" in names
    assert "Legacy Profile" in names, "profiles referenced by hosts stay selectable"
    for shipped in SHIPPED_TERMINAL_PROFILES:
        assert shipped in names
    assert names.count("Default") == 1, "duplicates are merged"

    by_name = {p["name"]: p for p in profiles}
    assert by_name["Default"]["source"] == "iterm2"
    assert by_name["Default"]["is_default"] is True
    assert by_name["connectify-PROD"]["source"] == "connectify"
    assert by_name["Legacy Profile"]["source"] == "host"


def test_list_available_profiles_without_iterm2(fake_home, monkeypatch):
    """No iTerm2 on the machine still yields the bundled profiles + Default."""
    monkeypatch.setattr(iterm_profiles, "_profiles_from_preferences", lambda: [])
    iterm_profiles.install_bundled_profiles(quiet=True)

    names = [p["name"] for p in iterm_profiles.list_available_profiles()]

    assert "Default" in names
    for shipped in SHIPPED_TERMINAL_PROFILES:
        assert shipped in names


def test_a_deleted_profile_stops_being_offered(fake_home, monkeypatch):
    """Removing a profile from iTerm2 must remove it from the picker too."""
    monkeypatch.setattr(iterm_profiles, "_profiles_from_preferences", lambda: [])
    iterm_profiles.install_bundled_profiles(quiet=True)

    removed = SHIPPED_TERMINAL_PROFILES[0]
    (dynamic_dir(fake_home) / f"{removed}.json").unlink()

    names = [p["name"] for p in iterm_profiles.list_available_profiles()]

    assert removed not in names, "a shipped profile the user deleted is gone for good"
    assert "Default" in names


def test_dynamic_folder_marks_third_party_profiles(fake_home):
    folder = dynamic_dir(fake_home)
    folder.mkdir(parents=True)
    (folder / "team-profiles.json").write_text(json.dumps({
        "Profiles": [{"Name": "Team Ops", "Guid": "team-guid"}]
    }))
    # A bare profile export (not wrapped in "Profiles") is read too
    (folder / "solo.json").write_text(json.dumps({"Name": "Solo", "Guid": "solo-guid"}))
    (folder / "broken.json").write_text("not json at all")

    profiles = {p["name"]: p for p in iterm_profiles._profiles_from_dynamic_folder()}

    assert profiles["Team Ops"]["source"] == "dynamic"
    assert profiles["Solo"]["source"] == "dynamic"

    assert "broken" not in profiles, "malformed files are skipped, not fatal"


# --- browser profiles --------------------------------------------------------

def test_is_browser_profile():
    assert iterm_profiles.is_browser_profile({"Custom Command": "Browser"}) is True
    assert iterm_profiles.is_browser_profile({"Custom Command": "browser"}) is True
    assert iterm_profiles.is_browser_profile({"Initial URL": "http://localhost:7890/"}) is True
    assert iterm_profiles.is_browser_profile({"Custom Command": "No"}) is False
    assert iterm_profiles.is_browser_profile({"Custom Command": "Yes", "Command": "ssh box"}) is False
    assert iterm_profiles.is_browser_profile({}) is False


def test_browser_profiles_are_installed_but_never_selectable(fake_home, monkeypatch):
    monkeypatch.setattr(iterm_profiles, "_profiles_from_preferences", lambda: [])

    iterm_profiles.install_bundled_profiles(quiet=True)

    for name in SHIPPED_BROWSER_PROFILES:
        assert (dynamic_dir(fake_home) / f"{name}.json").exists(), "browser profiles still get installed"

    names = [p["name"] for p in iterm_profiles.list_available_profiles()]
    for name in SHIPPED_BROWSER_PROFILES:
        assert name not in names, "browser profiles must not be offered for SSH hosts"


def test_browser_profiles_from_iterm2_are_excluded(fake_home, monkeypatch):
    """A user's own browser profiles are filtered out too, not just ours."""
    prefs = {
        "New Bookmarks": [
            {"Name": "Default", "Guid": "abc"},
            {"Name": "My Dashboard", "Guid": "def", "Custom Command": "Browser",
             "Initial URL": "https://example.com"},
        ],
        "Default Bookmark Guid": "abc",
    }
    monkeypatch.setattr(iterm_profiles, "_read_iterm_preferences", lambda: prefs)

    names = [p["name"] for p in iterm_profiles._profiles_from_preferences()]

    assert names == ["Default"]


def test_browser_profiles_in_dynamic_folder_are_excluded(fake_home):
    folder = dynamic_dir(fake_home)
    folder.mkdir(parents=True)
    (folder / "web.json").write_text(json.dumps({
        "Profiles": [
            {"Name": "Team Wiki", "Guid": "wiki", "Custom Command": "Browser",
             "Initial URL": "https://wiki.example.com"},
            {"Name": "Team Shell", "Guid": "shell"},
        ]
    }))

    names = [p["name"] for p in iterm_profiles._profiles_from_dynamic_folder()]

    assert names == ["Team Shell"]


# --- iTerm2 / browser plugin detection ---------------------------------------

@pytest.fixture
def fake_apps(tmp_path, monkeypatch):
    apps = tmp_path / "Applications"
    apps.mkdir()
    monkeypatch.setattr(iterm_profiles, "APP_SEARCH_PATHS", [str(apps)])
    monkeypatch.setattr(iterm_profiles, "_applescript_app_path", lambda bundle_id: None)
    return apps


def test_find_iterm2_uses_applescript_first(monkeypatch):
    monkeypatch.setattr(iterm_profiles, "_applescript_app_path",
                        lambda bundle_id: "/Applications/iTerm.app/"
                        if bundle_id == iterm_profiles.ITERM_BUNDLE_ID else None)

    assert iterm_profiles.find_iterm2() == "/Applications/iTerm.app/"


def test_find_apps_falls_back_to_applications_folder(fake_apps):
    """LaunchServices may not know a freshly copied app yet."""
    assert iterm_profiles.find_iterm2() is None
    assert iterm_profiles.find_browser_plugin() is None

    (fake_apps / "iTerm.app").mkdir()
    (fake_apps / "iTermBrowserPlugin.app").mkdir()

    assert iterm_profiles.find_iterm2() == str(fake_apps / "iTerm.app")
    assert iterm_profiles.find_browser_plugin() == str(fake_apps / "iTermBrowserPlugin.app")


def test_check_iterm2_requirements_reports_download_urls(fake_apps, capsys):
    status = iterm_profiles.check_iterm2_requirements()
    output = capsys.readouterr().out

    assert status == {"iterm2": None, "browser_plugin": None}
    assert iterm_profiles.ITERM_DOWNLOAD_URL in output
    assert iterm_profiles.BROWSER_PLUGIN_DOWNLOAD_URL in output


def test_warn_if_browser_plugin_missing(fake_apps, monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")

    iterm_profiles.warn_if_browser_plugin_missing()
    assert iterm_profiles.BROWSER_PLUGIN_DOWNLOAD_URL in capsys.readouterr().out

    (fake_apps / "iTermBrowserPlugin.app").mkdir()
    iterm_profiles.warn_if_browser_plugin_missing()
    assert capsys.readouterr().out == "", "no nagging once the plugin is installed"
