# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Connectify is a macOS-only SSH session launcher for iTerm2. It stores host definitions in JSON, passwords in the macOS Keychain, and opens sessions by driving iTerm2 through AppleScript. It ships to users as a PyInstaller bundle, not as a pip package.

**Platform constraint:** the core paths depend on `osascript`, `lsof`, iTerm2, and the macOS Keychain backend of `keyring`. Most runtime behavior cannot be exercised on Linux — expect to reason about changes statically rather than run them, unless you are on a Mac.

## Commands

```bash
make setup            # uv sync
make dev              # uv run python main.py  (interactive terminal picker)
make ui               # uv run python main.py --ui  (foreground web UI on :7860, opens browser)
make build            # uv run pyinstaller connectify.spec -> dist/connectify/
make dev-install      # build + ./dev-install.sh (installs to ~/.local)
make release          # build + tar dist/connectify-macos-arm64.tar.gz
make clean            # rm build/ dist/ __pycache__ etc.

uv run python main.py --list
uv run python main.py --debug          # dumps keychain state
uv run python main.py --ui --port 8080
uv add <package>                       # then add hidden imports to connectify.spec if needed
```

### Tests

`tests/test_api.py` exists but **pytest and httpx are not declared in `pyproject.toml`**, and there is no `make test` target. Run them with:

```bash
uv run --with pytest --with httpx pytest tests/
uv run --with pytest --with httpx pytest tests/test_api.py::test_create_host   # single test
```

The tests patch `api_server.api_manager.ssh_manager` and also mutate the module-level `api_manager` global directly, so they share state across the module — order matters and a new test should reset what it touches.

## Architecture

Three Python modules with a deliberately circular relationship:

- **`connectify.py`** — the shipped CLI entry point. Owns only the `connectify ui {start,stop,restart,logs,status}` subcommands; everything else is delegated to `main.main()`.
- **`main.py`** — `SSHManager`, the single source of truth for config, keychain, SSH command construction, and iTerm2 launching. Also owns the argparse surface for all non-`ui` flags.
- **`api_server.py`** — FastAPI app. `APISSHManager` is a thin wrapper that holds an `SSHManager` and adds caching/HTTP error mapping; it does not reimplement any SSH or keychain logic.

`api_server` imports `SSHManager` from `main`; `main.main()` imports `launch_api_server` from `api_server` when given `--ui`/`--silent`. Keep new domain logic in `SSHManager` so both the CLI and the web UI get it — putting it in `APISSHManager` silently makes it web-only.

### Two servers, two ports

- `connectify --ui` → foreground, port **7860** (`--port` overridable), opens a browser, binds `0.0.0.0` with `--share`.
- `connectify ui start` → background daemon, port **7890**, hardcoded in both `connectify.py` (`UI_PORT`) and `main.py`'s `--silent` branch. Changing the port means changing both.

The daemon's liveness check is `lsof -ti :7890`, not the PID file — `~/.connectify/ui.pid` is written for reference only and `stop` kills whatever holds the port. Logs go to `~/.connectify/ui.log`.

### Frozen vs. source dual-mode

Both entry points branch on whether they are running inside a PyInstaller bundle:

- `connectify.py:start_ui()` launches `sys.executable --silent` when `sys.frozen`, else `cd <script_dir> && uv run python main.py --silent`.
- `connectify.py:main()` tries `import main` first (works when bundled) and falls back to shelling out via `uv run`.

Any change to how the UI server is spawned has to work in both modes.

### Keychain storage (fragile — read before touching)

All passwords live in **one** keyring item: service `connectify-iterm2`, account `all_hosts`, value a JSON dict. This is deliberate — it means one Keychain permission prompt instead of one per host.

The dict key is `f"{username}@{hostname}"`. Callers pass a `service_name` of `f"ssh-{hostname}"`, and `store_password`/`get_password` strip the `ssh-` prefix to build the key. Changing the service name, account name, or key format orphans every existing user's stored passwords with no migration path.

### Password delivery to the SSH session

Passwords cannot be passed on the command line (the AppleScript command is visible), so:

1. The password is written to `~/.ssh_pass_{unix_timestamp}_{uuid8}` with mode `0600`.
2. `sshpass -f <file> ssh ...` is written into the new iTerm2 tab. `sshpass` is looked up via `which`, then `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`; if absent, it falls back to interactive password entry.
3. A **detached** `python3 -c 'sleep 60; unlink'` subprocess deletes the file.
4. Independently, every `SSHManager.__init__` starts a background thread (`cleanup_old_temp_files`) that sweeps `~/.ssh_pass_*` older than 5 minutes, parsing the timestamp out of the filename.

The filename format is load-bearing for step 4 — don't change it without updating the parser.

### iTerm2 launching and the concurrency lock

`launch_iterm_session` builds AppleScript that captures explicit `newTab`/`newWindow` → `targetSession` references before writing the SSH command, so a user switching tabs mid-launch doesn't get the command in the wrong tab. On top of that, `SSHManager._iterm_launch_lock` is a **class-level** `threading.Lock` that serializes the whole osascript block — necessary because the web UI's `/api/connect` spawns one thread per connection and users click multiple tiles at once.

Profile resolution falls back in order: requested profile → `"Default"` → `create tab with default profile`. Each fallback is a separate osascript invocation.

### Per-host SSH options

`resolve_ssh_options(host)` in `main.py` is the contract: a host's `ssh_options` list is used verbatim when present, and `None` (not present) falls back to `DEFAULT_SSH_OPTIONS[auth_method]`. An **empty list means "no extra options"** and is distinct from `None` — this is how hosts predating configurable options keep their old behavior. `HostModel.ssh_options` in `api_server.py` is `Optional[List[str]]` for the same reason; don't default it to `[]`.

### Config file and migration

`~/.connectify/hosts.json`. `SSHManager.__init__` calls `migrate_old_config()`, which moves `~/.ssh_manager_config.json` to the new location on first run and deletes the old file. Hosts are identified by their `name` field everywhere — it is the API path parameter and the key for update/delete — so names are effectively primary keys.

Alongside it in `~/.connectify/`: `ui.log`, `ui.pid`.

### Web UI

`static/index.html` is a single ~3200-line page with inline CSS/JS — no build step, no framework. It is **not** served as a file: `get_cached_html_content()` reads it into memory and `GET /` returns it inline, with a 5-minute TTL (`_static_file_cache`). This avoids filesystem lookups in a server that stays up for weeks and sidesteps PyInstaller path issues.

**Consequence for development:** edits to `index.html` may not appear for up to 5 minutes. Hit `POST /api/refresh-cache` or restart the server. `GET /api/cache-status` reports the cache state.

## Building and releasing

`connectify.spec` is the live PyInstaller config (entry scripts `connectify.py`, `main.py`, `api_server.py`); `launch.spec` is a legacy variant entered at `main.py` and is not used by the Makefile or CI. New third-party dependencies usually need entries in the spec's `hiddenimports` list, and anything under `static/` needs to stay in `datas`.

Releases are tag-driven: pushing `v*` runs `.github/workflows/release.yml`, which **overwrites `version.py`** with the tag version and build date, builds on `macos-latest`, and uploads `connectify-macos-arm64.tar.gz`. `version.py` in the repo reads `WIP-local-build`/`development` — leave it that way; don't hand-edit it for a release.

## Reference docs in-repo

`DEVELOPMENT.md` covers build/debug workflow in more depth. `CONFIG_MIGRATION.md` and `REPO_MIGRATION.md` are historical records of the config-path and repo-rename migrations. `TODO.md` holds planned features with implementation sketches.
