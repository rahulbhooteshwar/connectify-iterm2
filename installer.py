#!/usr/bin/env python3
"""
The installer's user interface.

`install.sh` is deliberately tiny: it only has to detect the architecture and
fetch the release archive, because the archive contains this program. Once it
is unpacked, the real installer runs from the binary itself - so the pretty
output costs the user no dependencies at all, and the same code handles
upgrades later (`connectify upgrade`), where it can show the download too.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn,
    TimeRemainingColumn, TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

import iterm_profiles

GITHUB_REPO = "rahulbhooteshwar/connectify-iterm2"
INSTALL_DIR = Path("~/.local/bin").expanduser()
LIB_DIR = Path("~/.local/lib/connectify").expanduser()

ITERM_URL = "https://iterm2.com/index.html"
BROWSER_PLUGIN_URL = "https://iterm2.com/browser-plugin.html"

console = Console()


def pretty(path):
    """Paths read better with $HOME collapsed to ~."""
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home):] if text.startswith(home) else text


# --- presentation ------------------------------------------------------------

def banner(subtitle):
    """The header every installer run opens with."""
    title = Text("Connectify", style="bold cyan")
    title.append("  SSH Session Manager for iTerm2", style="dim")
    console.print()
    console.print(Panel(Group(Align.center(title), Align.center(Text(subtitle, style="dim"))),
                        border_style="cyan", padding=(1, 2)))
    console.print()


def step(message):
    console.print(f"[cyan]›[/cyan] {message}")


def ok(message):
    console.print(f"  [green]✔[/green] {message}")


def warn(message):
    console.print(f"  [yellow]![/yellow] {message}")


def fail(message):
    console.print(f"  [red]✘[/red] {message}")


def link(url):
    return f"[link={url}]{url}[/link]"


# --- environment -------------------------------------------------------------

def check_requirements(strict=True):
    """Check what Connectify needs, reporting each item as it goes."""
    step("Checking requirements")

    if sys.platform != 'darwin':
        fail("Connectify only runs on macOS")
        return False
    ok(f"macOS ({os.uname().machine})")

    if os.geteuid() == 0:
        fail("Do not run the installer as root - it installs into your home directory")
        return False

    iterm = iterm_profiles.find_iterm2()
    if iterm:
        ok(f"iTerm2 [dim]{iterm}[/dim]")
    else:
        fail("iTerm2 is not installed")
        console.print(f"    Connectify launches every session in iTerm2: {link(ITERM_URL)}")
        if strict:
            return False

    plugin = iterm_profiles.find_browser_plugin()
    if plugin:
        ok(f"iTerm2 browser plugin [dim]{plugin}[/dim]")
    else:
        warn("iTerm2 browser plugin not found [dim](optional)[/dim]")
        console.print(f"    Needed only by the bundled [bold]connectify-UI[/bold] profile: "
                      f"{link(BROWSER_PLUGIN_URL)}")

    ssh = shutil.which('ssh')
    if ssh:
        ok(f"OpenSSH [dim]{ssh}[/dim]")
    else:
        warn("ssh not found on PATH")

    console.print()
    return True


# --- release downloads -------------------------------------------------------

def host_arch():
    machine = os.uname().machine
    return "arm64" if machine == "arm64" else "amd64"


def resolve_latest_version():
    """Ask GitHub for the latest published version."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "connectify-installer",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("tag_name", "").lstrip("v")


def download_release(version, arch, destination):
    """Download a release archive with a progress bar."""
    archive_name = f"connectify-macos-{arch}.tar.gz"
    url = (f"https://github.com/{GITHUB_REPO}/releases/download/v{version}/{archive_name}")

    step(f"Downloading Connectify [bold]v{version}[/bold] [dim]({arch})[/dim]")

    request = urllib.request.Request(url, headers={"User-Agent": "connectify-installer"})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as e:
        fail(f"Download failed ({e.code}) - {url}")
        if e.code == 404:
            console.print(f"    That release has no [bold]{archive_name}[/bold] build.")
        return None

    total = int(response.headers.get('Content-Length') or 0)
    target = Path(destination) / archive_name

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=32, complete_style="cyan"),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(archive_name, total=total or None)
        with open(target, 'wb') as f:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                progress.update(task, advance=len(chunk))

    size_mb = target.stat().st_size / 1024 / 1024
    ok(f"Downloaded {archive_name} [dim]({size_mb:.1f} MB)[/dim]")
    return target


def extract_release(archive, destination):
    step("Unpacking")
    with tarfile.open(archive) as tar:
        tar.extractall(destination)

    payload = Path(destination) / "connectify"
    if not (payload / "connectify").exists():
        fail("The archive did not contain a Connectify build")
        return None

    ok(f"Unpacked to [dim]{pretty(payload)}[/dim]")
    return payload


# --- installation ------------------------------------------------------------

def install_files(source):
    """Copy the build into ~/.local/lib and link it onto the PATH."""
    step("Installing")

    source = Path(source).resolve()
    if LIB_DIR.exists() and source.is_relative_to(LIB_DIR):
        ok("Already installed from this location")
    else:
        if LIB_DIR.exists():
            shutil.rmtree(LIB_DIR)
        LIB_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, LIB_DIR)
        ok(f"Copied into [dim]{pretty(LIB_DIR)}[/dim]")

    binary = LIB_DIR / "connectify"
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    symlink = INSTALL_DIR / "connectify"
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink()
    symlink.symlink_to(binary)
    ok(f"Linked [bold]{pretty(symlink)}[/bold]")

    return symlink


def install_profiles():
    step("Installing iTerm2 profiles")

    result = iterm_profiles.install_bundled_profiles(force=True, quiet=True)
    changed = result["installed"] + result["updated"]

    for name in sorted(changed):
        ok(f"{Path(name).stem}")
    for name in sorted(result["unchanged"]):
        ok(f"{Path(name).stem} [dim](already up to date)[/dim]")
    for error in result["errors"]:
        warn(error)

    if not result["errors"]:
        console.print(f"  [dim]{pretty(result['target_dir'])}[/dim]")


def check_path():
    """Tell the user how to put ~/.local/bin on PATH, if it isn't."""
    entries = os.environ.get('PATH', '').split(os.pathsep)
    if str(INSTALL_DIR) in entries:
        ok(f"{pretty(INSTALL_DIR)} is on your PATH")
        return True

    shell = os.environ.get('SHELL', '')
    profile = "~/.zshrc" if 'zsh' in shell else "~/.bashrc" if 'bash' in shell else "your shell profile"

    warn(f"{pretty(INSTALL_DIR)} is not on your PATH")
    console.print(Panel(
        f'echo \'export PATH="$HOME/.local/bin:$PATH"\' >> {profile}\n'
        f'source {profile}',
        title="Add it with", border_style="yellow", padding=(1, 2)))
    return False


def summary(version, arch, on_path):
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", justify="right")
    table.add_column()

    table.add_row("Version", f"[bold]v{version}[/bold]" if version else "[dim]unknown[/dim]")
    table.add_row("Architecture", arch)
    table.add_row("Installed to", pretty(LIB_DIR))
    table.add_row("Command", pretty(INSTALL_DIR / "connectify"))
    table.add_row("Config", "~/.connectify")

    commands = Table.grid(padding=(0, 2))
    commands.add_column(style="cyan")
    commands.add_column(style="dim")
    commands.add_row("connectify ui start", "Start the web UI in the background")
    commands.add_row("connectify ui status", "Check whether it is running")
    commands.add_row("connectify doctor", "Diagnostics")
    commands.add_row("connectify --help", "All commands")

    console.print()
    console.print(Panel(
        Group(
            Align.center(Text("🎉  Connectify is installed", style="bold green")),
            Text(""),
            table,
            Text(""),
            commands,
            Text(""),
            Text.from_markup("Hosts, credentials and themes live in the web UI: "
                             "[bold]http://localhost:7890[/bold]"),
        ),
        border_style="green", padding=(1, 2)))

    if not on_path:
        console.print("[yellow]Open a new terminal (or run the command above) "
                      "before using `connectify`.[/yellow]")
    console.print()


# --- entry points ------------------------------------------------------------

def run_install(source, version=None):
    """Install from an already-downloaded build (what install.sh calls)."""
    banner(f"Installing v{version}" if version else "Installing")

    if not check_requirements():
        return 1

    install_files(source)
    console.print()
    install_profiles()
    console.print()

    step("Finishing up")
    on_path = check_path()
    summary(version, host_arch(), on_path)
    return 0


def run_upgrade(version=None):
    """Download and install a release - used by `connectify upgrade`."""
    banner("Upgrading")

    if not check_requirements():
        return 1

    if not version:
        step("Looking up the latest release")
        try:
            version = resolve_latest_version()
        except (urllib.error.URLError, OSError, ValueError) as e:
            fail(f"Could not reach GitHub: {e}")
            return 1
        ok(f"Latest is [bold]v{version}[/bold]")
        console.print()

    with tempfile.TemporaryDirectory(prefix="connectify-upgrade-") as tmp:
        archive = download_release(version, host_arch(), tmp)
        if not archive:
            return 1

        payload = extract_release(archive, tmp)
        if not payload:
            return 1

        console.print()
        install_files(payload)
        console.print()
        install_profiles()
        console.print()

        step("Finishing up")
        on_path = check_path()
        summary(version, host_arch(), on_path)

    return 0
