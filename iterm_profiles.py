#!/usr/bin/env python3
"""
iTerm2 profile support for Connectify.

Two responsibilities:

1. Ship the Connectify profiles (``profiles/connectify-*.json``) and install
   them into iTerm2's Dynamic Profiles folder so they are available right
   after installing Connectify - no manual import needed.
2. Discover every profile iTerm2 knows about (regular profiles from its
   preferences plus dynamic profiles on disk) so the UI can offer all of them
   instead of a hardcoded list.

Everything here is best-effort: on a machine without iTerm2 (or a non-macOS
box, e.g. CI) the functions return empty results instead of raising.
"""

import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

# Profiles shipped with Connectify use this prefix, both as the file name and
# as the iTerm2 profile name.
PROFILE_PREFIX = "connectify-"

# iTerm2 reads every JSON file in this folder and merges the profiles it finds
# into its profile list. See https://iterm2.com/documentation-dynamic-profiles.html
DYNAMIC_PROFILES_DIR = "~/Library/Application Support/iTerm2/DynamicProfiles"

ITERM_BUNDLE_ID = "com.googlecode.iterm2"
BROWSER_PLUGIN_BUNDLE_ID = "com.googlecode.iterm2.iTermBrowserPlugin"

# Where macOS apps normally live, used as a fallback when LaunchServices
# doesn't know about a bundle yet (e.g. just copied into /Applications).
APP_SEARCH_PATHS = ["/Applications", "~/Applications"]
ITERM_APP_NAME = "iTerm.app"
BROWSER_PLUGIN_APP_NAME = "iTermBrowserPlugin.app"

ITERM_DOWNLOAD_URL = "https://iterm2.com/index.html"
BROWSER_PLUGIN_DOWNLOAD_URL = "https://iterm2.com/browser-plugin.html"

# Marker file recording the Connectify version whose profiles were last
# installed, so startup can skip the work on subsequent runs.
INSTALL_MARKER = "~/.connectify/.profiles_installed"


def dynamic_profiles_dir():
    """Path to iTerm2's DynamicProfiles folder (not guaranteed to exist)."""
    return Path(DYNAMIC_PROFILES_DIR).expanduser()


def bundled_profiles_dir():
    """Locate the ``profiles/`` folder shipped with this installation.

    Works both when running from source and from a PyInstaller bundle, where
    data files are extracted next to the executable or into ``sys._MEIPASS``.
    """
    candidates = []

    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / "profiles")

    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "profiles")
        candidates.append(exe_dir / "_internal" / "profiles")

    candidates.append(Path(__file__).resolve().parent / "profiles")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _load_profile_document(path):
    """Read a profile file and return its list of profile dictionaries.

    Accepts both the Dynamic Profile format (``{"Profiles": [...]}``) and a
    bare profile dictionary as exported from iTerm2's UI.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict) and isinstance(data.get('Profiles'), list):
        return [p for p in data['Profiles'] if isinstance(p, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def is_browser_profile(profile):
    """True for iTerm2 browser profiles (they open a web page, not a shell).

    iTerm2 marks these with ``"Custom Command": "Browser"``; the initial page
    lives in ``Initial URL``. They can't host an SSH session, so Connectify
    installs them but never offers them when configuring a host.
    """
    if not isinstance(profile, dict):
        return False
    if str(profile.get("Custom Command", "")).strip().lower() == "browser":
        return True
    return bool(str(profile.get("Initial URL", "")).strip())


def list_bundled_profiles():
    """Profiles shipped with Connectify, as ``{name, guid, badge, path}``."""
    profiles_dir = bundled_profiles_dir()
    if not profiles_dir:
        return []

    bundled = []
    for path in sorted(profiles_dir.glob("*.json")):
        try:
            for profile in _load_profile_document(path):
                bundled.append({
                    "name": profile.get("Name") or path.stem,
                    "guid": profile.get("Guid"),
                    "badge": profile.get("Badge Text"),
                    "is_browser": is_browser_profile(profile),
                    "path": str(path),
                })
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  Skipping malformed bundled profile {path.name}: {e}")
    return bundled


def install_bundled_profiles(force=False, quiet=False):
    """Copy the shipped profiles into iTerm2's DynamicProfiles folder.

    Idempotent: a profile is only written when it is missing or its content
    differs from the shipped version. Returns a summary dictionary.
    """
    result = {"installed": [], "updated": [], "unchanged": [], "errors": [], "target_dir": None}

    profiles_dir = bundled_profiles_dir()
    if not profiles_dir:
        result["errors"].append("Bundled profiles folder not found")
        if not quiet:
            print("⚠️  No bundled profiles found in this installation")
        return result

    target_dir = dynamic_profiles_dir()
    result["target_dir"] = str(target_dir)

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        result["errors"].append(f"Could not create {target_dir}: {e}")
        if not quiet:
            print(f"⚠️  Could not create {target_dir}: {e}")
        return result

    for source in sorted(profiles_dir.glob("*.json")):
        target = target_dir / source.name
        try:
            content = source.read_text(encoding='utf-8')
            # Validate before writing - a broken file would make iTerm2 ignore
            # the whole DynamicProfiles entry.
            json.loads(content)

            if target.exists() and not force:
                existing = target.read_text(encoding='utf-8')
                if existing == content:
                    result["unchanged"].append(source.name)
                    continue
                target.write_text(content, encoding='utf-8')
                result["updated"].append(source.name)
            else:
                was_present = target.exists()
                target.write_text(content, encoding='utf-8')
                (result["updated"] if was_present else result["installed"]).append(source.name)
        except (OSError, json.JSONDecodeError) as e:
            result["errors"].append(f"{source.name}: {e}")

    if not quiet:
        changed = result["installed"] + result["updated"]
        if changed:
            print(f"🎨 Installed {len(changed)} iTerm2 profile(s) into {target_dir}:")
            for name in changed:
                print(f"   • {Path(name).stem}")
        elif not result["errors"]:
            print(f"🎨 iTerm2 profiles already up to date ({target_dir})")
        for error in result["errors"]:
            print(f"⚠️  Profile install error - {error}")

    return result


def warn_if_browser_plugin_missing():
    """Point at the plugin download when a shipped browser profile needs it."""
    if sys.platform != 'darwin':
        return
    if not any(p.get('is_browser') for p in list_bundled_profiles()):
        return
    if find_browser_plugin():
        return

    print()
    print("⚠️  iTerm2 browser plugin is not installed")
    print("   The connectify-UI profile opens the Connectify web UI inside iTerm2 and needs it")
    print(f"   Get it from: {BROWSER_PLUGIN_DOWNLOAD_URL}")


def ensure_profiles_installed(version="unknown", quiet=True):
    """Install shipped profiles once per Connectify version.

    Called on startup so upgrades and source installs pick up new or changed
    profiles without the user re-running the installer. Set
    ``CONNECTIFY_SKIP_PROFILE_INSTALL=1`` to opt out entirely.
    """
    if os.environ.get('CONNECTIFY_SKIP_PROFILE_INSTALL', '').lower() in ('1', 'true', 'yes'):
        return None

    if sys.platform != 'darwin':
        return None

    marker = Path(INSTALL_MARKER).expanduser()
    try:
        if marker.exists() and marker.read_text(encoding='utf-8').strip() == str(version):
            return None
    except OSError:
        pass

    result = install_bundled_profiles(quiet=quiet)

    if not result["errors"]:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(version), encoding='utf-8')
        except OSError:
            pass

    return result


def _applescript_app_path(bundle_id):
    """Ask Finder (via AppleScript) where an app bundle lives, or None."""
    script = (
        f'tell application "Finder" to get POSIX path of '
        f'(application file id "{bundle_id}" as alias)'
    )
    try:
        completed = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    path = completed.stdout.strip()
    return path or None


def _find_app(bundle_id, app_name):
    """Locate an app by bundle id, falling back to the usual app folders.

    The fallback matters right after a download: an app copied into
    /Applications may not be registered with LaunchServices yet, so the
    AppleScript lookup fails even though the app is there.
    """
    path = _applescript_app_path(bundle_id)
    if path:
        return path

    for base in APP_SEARCH_PATHS:
        candidate = Path(base).expanduser() / app_name
        if candidate.exists():
            return str(candidate)

    return None


def find_iterm2():
    """Path to iTerm2, or None if it isn't installed."""
    return _find_app(ITERM_BUNDLE_ID, ITERM_APP_NAME)


def find_browser_plugin():
    """Path to the iTerm2 browser plugin, or None if it isn't installed."""
    return _find_app(BROWSER_PLUGIN_BUNDLE_ID, BROWSER_PLUGIN_APP_NAME)


def check_iterm2_requirements(quiet=False):
    """Report whether iTerm2 and its browser plugin are installed."""
    status = {
        "iterm2": find_iterm2(),
        "browser_plugin": find_browser_plugin(),
    }

    if quiet:
        return status

    if status["iterm2"]:
        print(f"✅ iTerm2 found: {status['iterm2']}")
    else:
        print("❌ iTerm2 is not installed")
        print(f"   Install it from: {ITERM_DOWNLOAD_URL}")

    if status["browser_plugin"]:
        print(f"✅ iTerm2 browser plugin found: {status['browser_plugin']}")
    else:
        print("⚠️  iTerm2 browser plugin is not installed")
        print("   The connectify-UI profile opens the Connectify web UI inside iTerm2 and needs it")
        print(f"   Get it from: {BROWSER_PLUGIN_DOWNLOAD_URL}")

    return status


def _read_plist(path):
    try:
        with open(path, 'rb') as f:
            return plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None


def _read_iterm_preferences():
    """Load iTerm2's preferences, honouring a custom preferences folder.

    Prefers ``defaults export`` (reads through the preferences daemon, so it
    reflects unsaved in-memory changes) and falls back to reading the plist
    file directly.
    """
    prefs = None

    try:
        completed = subprocess.run(
            ['defaults', 'export', ITERM_BUNDLE_ID, '-'],
            capture_output=True, timeout=5,
        )
        if completed.returncode == 0 and completed.stdout:
            prefs = plistlib.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        prefs = None

    if not prefs:
        prefs = _read_plist(Path(f"~/Library/Preferences/{ITERM_BUNDLE_ID}.plist").expanduser())

    if not prefs:
        return None

    # iTerm2 can be configured to load its preferences from a custom folder;
    # in that case the profile list lives there.
    custom_folder = prefs.get('PrefsCustomFolder')
    if prefs.get('LoadPrefsFromCustomFolder') and custom_folder:
        custom_plist = Path(str(custom_folder)).expanduser() / f"{ITERM_BUNDLE_ID}.plist"
        custom_prefs = _read_plist(custom_plist)
        if custom_prefs and custom_prefs.get('New Bookmarks'):
            return custom_prefs

    return prefs


def _profiles_from_preferences():
    prefs = _read_iterm_preferences()
    if not prefs:
        return []

    bookmarks = prefs.get('New Bookmarks') or []
    default_guid = prefs.get('Default Bookmark Guid')

    profiles = []
    for bookmark in bookmarks:
        if not isinstance(bookmark, dict):
            continue
        name = bookmark.get('Name')
        if not name or is_browser_profile(bookmark):
            continue
        profiles.append({
            "name": str(name),
            "guid": bookmark.get('Guid'),
            "source": "iterm2",
            "is_default": bool(default_guid) and bookmark.get('Guid') == default_guid,
        })
    return profiles


def _profiles_from_dynamic_folder():
    folder = dynamic_profiles_dir()
    if not folder.is_dir():
        return []

    profiles = []
    for path in sorted(folder.iterdir()):
        if path.name.startswith('.') or not path.is_file():
            continue
        try:
            for profile in _load_profile_document(path):
                name = profile.get('Name')
                if not name or is_browser_profile(profile):
                    continue
                profiles.append({
                    "name": str(name),
                    "guid": profile.get('Guid'),
                    "source": "connectify" if path.name.startswith(PROFILE_PREFIX) else "dynamic",
                    "is_default": False,
                })
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # Not every file in that folder is necessarily a profile we can read
            continue
    return profiles


def list_available_profiles(extra_names=None):
    """Every iTerm2 profile Connectify can offer, sorted by name.

    Merges iTerm2's own profiles with the dynamic profiles on disk (including
    the ones shipped by Connectify, while they are still installed).
    "Default" is always present.

    ``extra_names`` forces additional names into the list. It is deliberately
    not fed from the configured hosts: a profile deleted in iTerm2 has to
    disappear from the picker even if hosts still reference it.
    """
    collected = []
    try:
        collected.extend(_profiles_from_preferences())
    except Exception:  # pragma: no cover - defensive, discovery must never fail
        pass
    try:
        collected.extend(_profiles_from_dynamic_folder())
    except Exception:  # pragma: no cover - defensive, discovery must never fail
        pass

    # The shipped profiles, but only the ones still installed: deleting one
    # from the DynamicProfiles folder has to take it out of the picker too,
    # otherwise Connectify keeps offering a profile iTerm2 no longer has.
    installed_dir = dynamic_profiles_dir()
    for bundled in list_bundled_profiles():
        if bundled.get("is_browser"):
            continue
        if not (installed_dir / Path(bundled["path"]).name).exists():
            continue
        collected.append({
            "name": bundled["name"],
            "guid": bundled.get("guid"),
            "source": "connectify",
            "is_default": False,
        })

    for name in (extra_names or []):
        if name:
            collected.append({"name": str(name), "guid": None, "source": "host", "is_default": False})

    collected.append({"name": "Default", "guid": None, "source": "iterm2", "is_default": False})

    # De-duplicate by profile name, keeping the most informative source.
    source_rank = {"iterm2": 0, "connectify": 1, "dynamic": 2, "host": 3}
    merged = {}
    for profile in collected:
        name = profile["name"]
        existing = merged.get(name)
        if existing is None:
            merged[name] = profile
            continue
        if source_rank.get(profile["source"], 9) < source_rank.get(existing["source"], 9):
            profile["is_default"] = profile["is_default"] or existing["is_default"]
            merged[name] = profile
        elif profile["is_default"]:
            existing["is_default"] = True

    return sorted(merged.values(), key=lambda p: p["name"].lower())


def print_profiles_status():
    """CLI helper: show shipped profiles and what iTerm2 currently exposes."""
    bundled = list_bundled_profiles()
    target_dir = dynamic_profiles_dir()

    print("🎨 Connectify iTerm2 Profiles")
    print("=" * 60)
    check_iterm2_requirements()
    print()
    print(f"Bundled with this install : {len(bundled)}")
    for profile in bundled:
        installed = (target_dir / f"{profile['name']}.json").exists()
        status = "✅ installed" if installed else "⬜ not installed"
        badge = f" (badge: {profile['badge']})" if profile.get('badge') else ""
        kind = " [browser profile]" if profile.get('is_browser') else ""
        print(f"   • {profile['name']}{badge}{kind} - {status}")

    print(f"\nDynamic profiles folder   : {target_dir}")

    available = list_available_profiles()
    print(f"\nProfiles selectable for hosts: {len(available)}")
    print("(browser profiles are installed but never offered for SSH hosts)")
    for profile in available:
        marker = " (default)" if profile.get('is_default') else ""
        print(f"   • {profile['name']} [{profile['source']}]{marker}")
