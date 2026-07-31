import json
import os
import sys
from pathlib import Path

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import iterm_profiles


REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_PROFILES = ["connectify-PERSONAL", "connectify-PROD", "connectify-NONPROD"]


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


def test_list_bundled_profiles():
    bundled = iterm_profiles.list_bundled_profiles()
    assert {p["name"] for p in bundled} == set(SHIPPED_PROFILES)


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

    import main

    main.SSHManager(str(fake_home / ".connectify/hosts.json"))

    for name in SHIPPED_PROFILES:
        assert (dynamic_dir(fake_home) / f"{name}.json").exists()
    assert "Installed Connectify iTerm2 profiles" in capsys.readouterr().out


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
    for shipped in SHIPPED_PROFILES:
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

    names = [p["name"] for p in iterm_profiles.list_available_profiles()]

    assert "Default" in names
    for shipped in SHIPPED_PROFILES:
        assert shipped in names


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
