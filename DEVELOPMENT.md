# Connectify - Development Guide

This guide is for developers who want to contribute to Connectify or build it from source.

## Prerequisites for Development

- macOS
- iTerm2
- Python 3.12+
- **uv** (recommended) - Fast Python package manager

**Note**: End users don't need any of these! They can install via the one-line installer which downloads pre-built binaries.

## Setup Development Environment

### 1. Install uv (if not already installed)

**Option A: Using Homebrew (Recommended)**
```bash
brew install uv
```

**Option B: Using curl**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Option C: Using pip**
```bash
pip install uv
```

### 2. Clone and Setup Project

```bash
# Clone the repository
git clone https://github.com/rahulbhooteshwar/connectify-iterm2.git
cd connectify-iterm2

# Install dependencies
make setup

# Verify installation
uv run python connectify.py --help
```

## Development Workflow

### Running in Development Mode

```bash
# Web interface (foreground)
make ui

# Run with arguments
uv run python main.py --ui --port 8080
uv run python connectify.py doctor
```

### Building the Executable

```bash
# Build standalone executable
make build

# Build and test local installation
make test-install

# Clean build artifacts
make clean
```

### Manual Development Commands

```bash
# Install/update dependencies
uv sync

# Add new dependency
uv add <package-name>

# Run the web UI
uv run python main.py --ui

# Build executable manually
uv run pyinstaller connectify.spec

# Install locally (no sudo needed)
mkdir -p ~/.local/bin ~/.local/lib/connectify
cp -R ./dist/connectify/* ~/.local/lib/connectify/
ln -sf ~/.local/lib/connectify/connectify ~/.local/bin/connectify
```

## Project Structure

```
connectify/
├── connectify.py              # User-facing CLI (ui / profiles / doctor)
├── main.py                    # Core SSH manager functionality
├── api_server.py              # FastAPI web server
├── iterm_profiles.py          # Bundled profile install + iTerm2 discovery
├── vault.py                   # Encrypted credentials vault (AES-256-GCM + scrypt)
├── ssh_session.py             # Leak-free session launch (askpass over a FIFO)
├── profiles/                  # iTerm2 profiles shipped with Connectify
│   ├── connectify-PERSONAL.json
│   ├── connectify-NONPROD.json
│   ├── connectify-PROD.json
│   └── connectify-UI.json     # Browser profile for the web UI
├── connectify.spec            # PyInstaller build configuration
├── pyproject.toml             # Python dependencies
├── Makefile                   # Build automation
├── install.sh                 # Installation script
├── uninstall.sh               # Uninstallation script
├── static/                    # Web UI assets
│   ├── index.html            # Single-page web interface
│   └── vendor/               # Vendored assets - the UI loads no CDNs at runtime
│       ├── fontawesome/      # Icon font (solid + regular)
│       └── montserrat/       # UI typeface (variable, latin + latin-ext)
├── tests/                     # Test files
└── docs/                      # Documentation
    ├── README.md             # User documentation
    ├── DEVELOPMENT.md        # This file
    └── DISTRIBUTION_CHECKLIST.md
```

## Key Components

### 1. connectify.py - The CLI

The entire user-facing command line. Deliberately small: hosts, groups, themes
and connections are managed in the web UI, so the CLI only covers

- UI server management (`ui start|stop|restart|status|logs`)
- Bundled iTerm2 profiles (`profiles install|list`)
- Diagnostics (`doctor`) and `version`
- Internally, `--silent`/`--ui` hand off to `main.main()` to run the server -
  this is how `ui start` relaunches the executable in the background

Works with both the PyInstaller bundle and the source checkout.

### 2. main.py - Core Functionality

The SSH engine behind the web UI:
- SSH host configuration (load/save/CRUD)
- iTerm2 session launching, using a credential resolved from the vault. Launches
  are serialized and spaced (`LAUNCH_SETTLE_SECONDS`), the AppleScript returns
  the new session's id so a silent failure can't look like success, transient
  AppleScript errors are retried once, and a failed launch cleans up its
  session directory
- Credential associations: which hosts use a credential and renaming
- `clean_legacy_host_fields()` strips pre-vault auth fields from hosts.json on
  startup, materialising the SSH options they implied first
- `main()` starts the web server (no interactive terminal UI)

### 2b. vault.py - Credentials Vault

`~/.connectify/vault.json`, AES-256-GCM with a scrypt-derived key:
- `Vault` handles create/unlock/change-passcode and credential CRUD. Everything
  needs the derived key, so a locked vault simply can't be read.
- `VaultSessions` keeps unlocked keys in server memory only, keyed by an opaque
  token handed to the browser tab. Nothing is persisted, so a page reload
  re-locks the vault; sessions also expire when idle. The UI asks for the
  passcode on load and revokes its token via `sendBeacon` on `pagehide`, so the
  vault's unlocked window is exactly the app's lifetime.
- The API layer passes the token in the `X-Vault-Token` header and answers a
  locked vault with `401 {"code": "vault_locked"}`, which the UI turns into the
  unlock dialog (and retries the original request afterwards).

### 2c. ssh_session.py - Launching Sessions

Builds everything a session needs without ever putting a secret on disk or on a
command line:
- `build_ssh_argv()` - the ssh command line (no secrets, no sshpass)
- `SecretChannel` - a FIFO in a private 0700 directory that hands the password
  or key passphrase to ssh's askpass helper, a bounded number of times and only
  for a limited window. The FIFO is replaced between hand-offs so a draining
  reader can't pick up a second copy.
- `prepare_session()` - writes the askpass helper and the launcher script, then
  arms the channel. `main.py` passes `session.command` to iTerm2 as the session
  *command*, so no shell runs it and nothing reaches the shell history.

Requires OpenSSH 8.4+ (`SSH_ASKPASS_REQUIRE=force`); older versions fall back to
prompting in the terminal. `connectify doctor` reports the installed version.

### 3. iterm_profiles.py - iTerm2 Profiles

Handles:
- Installing `profiles/connectify-*.json` into
  `~/Library/Application Support/iTerm2/DynamicProfiles/` (idempotent, runs on
  install and once per version at startup)
- Discovering every available profile from iTerm2's preferences and the
  DynamicProfiles folder, which feeds `GET /api/profiles` and the UI dropdown.
  Browser profiles (`"Custom Command": "Browser"` / an `Initial URL`) are
  filtered out - they can't host an SSH session - so `connectify-UI` is
  installed but never offered when configuring a host
- Locating iTerm2 and its browser plugin by bundle id via AppleScript
  (`com.googlecode.iterm2` / `com.googlecode.iterm2.iTermBrowserPlugin`),
  falling back to `/Applications`. The installers use the same logic in bash:
  a missing iTerm2 aborts installation, a missing plugin only warns.

To add a new bundled profile: export it from iTerm2, save it as
`profiles/connectify-<NAME>.json` in the Dynamic Profile format
(`{"Profiles": [ ... ]}`) with a unique `Guid` and a `Name` that matches the
file name. It is picked up by the build and installers automatically.

### 4. api_server.py - Web Server

Handles:
- FastAPI web server
- REST API endpoints
- Static file serving
- CORS configuration

### 5. static/index.html - Web UI

Single-page application with:
- Tile-based host display grouped by each host's `group` (ungrouped hosts are
  rendered as-is, after the groups)
- Per-host tile theme (`default`/`red`/`green`/`orange`), picked with the colour
  dots in the add/edit form - `GET /api/groups` feeds the group picker
- Real-time search and filtering (tags remain search/filter only)
- The Vault page (toolbar lock icon): unlock, credential CRUD, host associations
- One message style throughout: a slim pill at the bottom of the window
- Launching shows a spinner on the tile for as long as the launch actually
  takes - `POST /api/connect` only answers once iTerm2 has opened the tab
- Responsive design

## Building and Packaging

### PyInstaller Configuration

The `connectify.spec` file configures PyInstaller to:
- Bundle all Python dependencies
- Include static web assets
- Create a directory-based distribution (not single-file)
- Exclude user config files

### Build Process

```bash
# 1. Clean previous builds
make clean

# 2. Build executable
make build

# This creates:
# dist/connectify/
#   ├── connectify           # Main executable
#   └── _internal/           # Bundled dependencies and assets
```

### Installation Process

The `install.sh` script:
1. Checks for dependencies (Python 3.12+)
2. Detects installation mode (local source vs remote)
3. Builds from source if needed
4. Installs to `/usr/local/lib/connectify/`
5. Creates symlink at `/usr/local/bin/connectify`
6. Verifies installation

## Testing

### Manual Testing

```bash
# Test executable directly
./dist/connectify/connectify --help
./dist/connectify/connectify ui status
./dist/connectify/connectify doctor

# Test installation
./install.sh
connectify --help
connectify ui start

# Test uninstallation
./uninstall.sh
```

### Test Checklist

- [ ] Build succeeds without errors
- [ ] Executable runs and shows help
- [ ] `ui start|stop|restart|status|logs`, `profiles`, `doctor` and `version` work
- [ ] UI server starts and stops correctly
- [ ] Web interface is accessible
- [ ] SSH connections work
- [ ] Configuration is preserved
- [ ] Keychain integration works
- [ ] Installation script works
- [ ] Uninstallation script works

## Adding New Features

### Adding a New CLI Command

The CLI stays intentionally minimal - prefer adding features to the web UI.
If a command genuinely belongs on the command line:

1. Add it to the dispatcher in `connectify.py`
2. Add it to `USAGE` in the same file
3. Update documentation
4. Test thoroughly

### Adding a New UI Feature

1. Update `api_server.py` for backend
2. Update `static/index.html` for frontend
3. Test with `make ui`
4. Rebuild and test: `make build`

### Adding a New Dependency

```bash
# Add to project
uv add <package-name>

# Update PyInstaller spec if needed
# Edit connectify.spec to add hidden imports

# Rebuild
make clean
make build
```

## Debugging

### Debug Build Issues

```bash
# Check build warnings
cat build/connectify/warn-connectify.txt

# Check cross-references
open build/connectify/xref-connectify.html

# Verbose build
uv run pyinstaller --log-level DEBUG connectify.spec
```

### Debug Runtime Issues

```bash
# Full diagnostics
connectify doctor

# Check UI logs
tail -f ~/.connectify/ui.log

# Check if port is in use
lsof -i :7890

# Test in development mode
uv run python connectify.py doctor
```

### Common Issues

**Issue**: PyInstaller missing imports
- **Solution**: Add to `hiddenimports` in `connectify.spec`

**Issue**: Static files not found
- **Solution**: Check `datas` in `connectify.spec`

**Issue**: Executable won't run
- **Solution**: Check macOS Gatekeeper settings: `xattr -d com.apple.quarantine dist/connectify/connectify`

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small
- Use type hints where appropriate

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and commit
git add .
git commit -m "Add your feature"

# Push and create PR
git push origin feature/your-feature
```

## Release Process

See `DISTRIBUTION_CHECKLIST.md` for complete release process.

### Quick Release

```bash
# 1. Update version in pyproject.toml
# 2. Build release
make clean
make build

# 3. Create release archive
cd dist
tar -czf connectify-macos-arm64.tar.gz connectify/

# 4. Create GitHub release and upload archive
# 5. Update install.sh if needed
```

## Performance Optimization

### Build Size

Current build size: ~6MB executable + ~15MB dependencies

To reduce:
- Remove unused dependencies
- Use UPX compression (already enabled)
- Exclude unnecessary modules in spec file

### Runtime Performance

- SSH connections are instant (native SSH)
- Web UI loads in <100ms
- Interactive menu is responsive
- Background server uses minimal resources

## Security Considerations

- Passwords stored in macOS Keychain (secure)
- SSH keys use standard SSH authentication
- Web server binds to localhost by default
- No telemetry or external connections
- Temporary files have secure permissions (0600)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Distribution & Release Process

### Pre-Release Checklist

1. **Verify GitHub URLs** in:
   - `install.sh` (line 11: `GITHUB_REPO="rahulbhooteshwar/connectify-iterm2"`)
   - `uninstall.sh` (bottom of file)
   - `README.md` (all instances should reference correct repo)

2. **Test locally**:
   ```bash
   # Build
   make build
   
   # Test executable
   ./dist/connectify/connectify --help
   
   # Test local installation
   make dev-install
   connectify --help
   connectify ui start
   ```

3. **Create release**:
   ```bash
   # Commit changes
   git add .
   git commit -m "Release v1.0.0"
   git push origin main
   
   # Push version tag (triggers GitHub Actions)
   git tag v1.0.0
   git push origin v1.0.0
   ```

GitHub Actions will automatically build and publish the release!

### Manual Release (If Needed)

If you need to create a release manually:

1. **Build and create archive**:
   ```bash
   make release
   ```

2. **Create GitHub Release**:
   - Go to GitHub → Releases → New Release
   - Tag: `v1.0.0`
   - Title: `Connectify v1.0.0`
   - Upload: `dist/connectify-macos-arm64.tar.gz`

3. **Test installation**:
   ```bash
   curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/install.sh | sh
   ```

## Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [macOS Keychain Services](https://developer.apple.com/documentation/security/keychain_services)

## Support

For development questions:
- Repository: https://github.com/rahulbhooteshwar/connectify-iterm2
- Issues: https://github.com/rahulbhooteshwar/connectify-iterm2/issues
- Discussions: https://github.com/rahulbhooteshwar/connectify-iterm2/discussions

---

Built with ❤️ by RB (Rahul Bhooteshwar)
