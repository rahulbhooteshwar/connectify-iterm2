#!/usr/bin/env python3
"""
Development tasks for Connectify - run with `uv run tasks.py <name>`.

This replaces the Makefile: the project already needs uv and Python, so the
tasks live in the same toolchain as the code instead of a second one.

    uv run tasks.py            # list the tasks
    uv run tasks.py ui         # run the web interface
    uv run tasks.py build      # build the standalone executable
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
UI = ROOT / "ui"
STATIC = ROOT / "static"

# Release archives are named after the architecture they were built for
ARCH_ALIASES = {"x86_64": "amd64", "arm64": "arm64"}

TASKS = {}


def task(help_text):
    def register(func):
        TASKS[func.__name__.replace('_', '-')] = (func, help_text)
        return func
    return register


def run(*command, **kwargs):
    """Run a command, echoing it first, and stop the task if it fails."""
    printable = ' '.join(str(part) for part in command)
    print(f"$ {printable}")
    kwargs.setdefault("cwd", ROOT)
    result = subprocess.run([str(part) for part in command], **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result


def host_arch():
    machine = platform.machine()
    return ARCH_ALIASES.get(machine, machine)


@task("Install/refresh the development environment")
def setup():
    run("uv", "sync")
    print("✅ Environment ready")


@task("Run the web interface in the foreground (opens a browser)")
def ui():
    run("uv", "run", "python", "main.py", "--ui")


@task("Build the React interface into static/ (needs Node)")
def ui_build():
    if shutil.which("npm") is None:
        sys.exit("❌ npm is required to build the interface (https://nodejs.org)")
    if not (UI / "node_modules").exists():
        run("npm", "ci", cwd=UI)
    run("npm", "run", "build", cwd=UI)
    print(f"✅ Built {STATIC.relative_to(ROOT)}")


@task("Run the interface in watch mode against a running backend")
def ui_dev():
    run("npm", "run", "dev", cwd=UI)


@task("Run the test suite")
def test():
    run("uv", "run", "--with", "pytest", "--with", "httpx", "pytest", "tests", "-q")


@task("Build the standalone executable into dist/")
def build():
    # static/ is committed, but PyInstaller bundles whatever is on disk - build
    # the interface first so the executable can never ship a stale one.
    ui_build()
    run("uv", "run", "pyinstaller", "connectify.spec", "--noconfirm")
    binary = DIST / "connectify" / "connectify"
    if not binary.exists():
        sys.exit("❌ Build finished but the executable is missing")
    print(f"✅ Built {binary} ({host_arch()})")


@task("Build, then install locally to ~/.local (the same UI a real install shows)")
def install():
    build()
    run(DIST / "connectify" / "connectify", "install", "--from", str(DIST / "connectify"))


@task("Build and archive a release tarball for this machine's architecture")
def release():
    build()
    archive = DIST / f"connectify-macos-{host_arch()}.tar.gz"
    run("tar", "-czf", str(archive), "-C", str(DIST), "connectify")
    print(f"✅ {archive}")
    print()
    print("To publish a release (CI builds both arm64 and amd64):")
    print("  • push a version tag:  git tag v2.0.1 && git push origin v2.0.1")
    print("  • or run the 'Build and Release' workflow with a version input")


@task("Remove build artefacts and caches")
def clean():
    for path in (DIST, BUILD, ROOT / ".pytest_cache"):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            print(f"removed {path.relative_to(ROOT)}")
    for cache in ROOT.rglob("__pycache__"):
        if ".venv" not in str(cache):
            shutil.rmtree(cache, ignore_errors=True)
    print("✅ Clean")


def main():
    args = sys.argv[1:]
    name = args[0] if args else None

    if not name or name in ("-h", "--help", "help"):
        width = max(len(n) for n in TASKS)
        print(__doc__.strip().split('\n')[0])
        print()
        print("Tasks:")
        for task_name, (_, help_text) in TASKS.items():
            print(f"  uv run tasks.py {task_name:<{width}}   {help_text}")
        print()
        print("End users install with:")
        print("  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/"
              "connectify-iterm2/main/install.sh | sh")
        return 0

    if name not in TASKS:
        print(f"❌ Unknown task: {name}")
        print(f"   Available: {', '.join(TASKS)}")
        return 1

    TASKS[name][0]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
