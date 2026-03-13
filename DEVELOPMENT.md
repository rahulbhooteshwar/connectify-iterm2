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
git clone https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager.git
cd iterm2-ssh-session-manager

# Install dependencies
make setup

# Verify installation
uv run python main.py --help
```

## Development Workflow

### Running in Development Mode

```bash
# Terminal interface
make dev

# Web interface
make ui

# Run with arguments
uv run python main.py --list
uv run python main.py --ui --port 8080
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

# Run the application
uv run python main.py

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
├── connectify.py              # CLI wrapper with ui subcommands
├── main.py                    # Core SSH manager functionality
├── api_server.py              # FastAPI web server
├── connectify.spec            # PyInstaller build configuration
├── pyproject.toml             # Python dependencies
├── Makefile                   # Build automation
├── install.sh                 # Installation script
├── uninstall.sh               # Uninstallation script
├── static/                    # Web UI assets
│   └── index.html            # Single-page web interface
├── tests/                     # Test files
└── docs/                      # Documentation
    ├── README.md             # User documentation
    ├── DEVELOPMENT.md        # This file
    └── DISTRIBUTION_CHECKLIST.md
```

## Key Components

### 1. connectify.py - CLI Wrapper

Handles:
- UI server management (start, stop, restart, logs, status)
- Delegation to main.py for SSH functionality
- Works with both PyInstaller bundle and source code

### 2. main.py - Core Functionality

Handles:
- SSH host management
- Interactive host selection
- Keychain integration
- iTerm2 profile support
- Configuration management

### 3. api_server.py - Web Server

Handles:
- FastAPI web server
- REST API endpoints
- Static file serving
- CORS configuration

### 4. static/index.html - Web UI

Single-page application with:
- Tile-based host display
- Real-time search and filtering
- Tag-based organization
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
- [ ] All CLI commands work
- [ ] UI server starts and stops correctly
- [ ] Web interface is accessible
- [ ] SSH connections work
- [ ] Configuration is preserved
- [ ] Keychain integration works
- [ ] Installation script works
- [ ] Uninstallation script works

## Adding New Features

### Adding a New CLI Command

1. Update `connectify.py` to add the command
2. Update help text in `main.py`
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
# Run with debug flag
connectify --debug

# Check UI logs
tail -f ~/.connectify/ui.log

# Check if port is in use
lsof -i :7890

# Test in development mode
uv run python main.py --debug
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
   - `install.sh` (line 11: `GITHUB_REPO="rahulbhooteshwar/iterm2-ssh-session-manager"`)
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
   curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/install.sh | sh
   ```

## Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [macOS Keychain Services](https://developer.apple.com/documentation/security/keychain_services)

## Support

For development questions:
- Repository: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager
- Issues: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager/issues
- Discussions: https://github.com/rahulbhooteshwar/iterm2-ssh-session-manager/discussions

---

Built with ❤️ by RB (Rahul Bhooteshwar)
