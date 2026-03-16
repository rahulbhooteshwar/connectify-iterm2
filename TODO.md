# Connectify - TODO List

## Planned Features & Improvements

### 0. Fix tab interferrence issue ... launch something when it is launching.. change tab... it launches in current tab !! How to ensure it always launches it in the tab designated ... use some unique tab id.. & launch session in that only

### 1. iTerm2 Installation Detection ⏳

**Priority:** High
**Status:** Planned

**Description:**
Add iTerm2 installation detection during the Connectify installation process. If iTerm2 is not installed, fail the installation gracefully and guide users to install it first.

**Requirements:**
- Detect iTerm2 installation at the time of installing Connectify
- If not found, fail installation with clear error message
- Provide installation guidance with official iTerm2 download URL
- Check for iTerm2 in standard macOS application locations

**Implementation Details:**
```bash
# In install.sh, add before main installation:
check_iterm2() {
    if [[ ! -d "/Applications/iTerm.app" ]]; then
        print_error "iTerm2 is required but not installed"
        echo ""
        print_info "Please install iTerm2 first:"
        echo "  https://iterm2.com/downloads.html"
        echo ""
        print_info "Or install via Homebrew:"
        echo "  brew install --cask iterm2"
        echo ""
        exit 1
    fi
    print_success "iTerm2 detected"
}
```

**Files to Update:**
- `install.sh` - Add iTerm2 detection check
- `dev-install.sh` - Add iTerm2 detection check
- `README.md` - Update requirements section to emphasize iTerm2 requirement

---

### 2. iTerm2 Profile Management 🎨

**Priority:** Medium
**Status:** Planned

**Description:**
Package default iTerm2 profiles with Connectify and provide commands to install/manage them. This will give users pre-configured, visually appealing profiles for different environments (production, staging, development, etc.).

**Requirements:**
- Package default iTerm2 profiles with the tool
- Provide command to install profiles: `connectify profiles install`
- Detect profile conflicts with existing user profiles
- Fail gracefully if conflicts exist
- Allow override with explicit flag: `connectify profiles install --override`
- List available profiles: `connectify profiles list`
- Show installed profiles: `connectify profiles status`

**Proposed Commands:**
```bash
# List available bundled profiles
connectify profiles list

# Check which profiles are installed
connectify profiles status

# Install all bundled profiles (fails if conflicts exist)
connectify profiles install

# Install with override (replaces existing profiles)
connectify profiles install --override

# Install specific profile
connectify profiles install --name "Production"

# Backup existing profiles before install
connectify profiles backup

# Restore backed up profiles
connectify profiles restore
```

**Profile Categories:**
- **Production** - Red theme, bold indicators, high visibility
- **Staging** - Yellow/orange theme, warning colors
- **Development** - Green theme, comfortable for long sessions
- **Database** - Blue theme, distinct for DB connections
- **Personal** - Purple/custom theme for personal servers

**Implementation Details:**

1. **Profile Storage:**
   ```
   ~/.local/lib/connectify/
   └── profiles/
       ├── Production.json
       ├── Staging.json
       ├── Development.json
       ├── Database.json
       └── Personal.json
   ```

2. **iTerm2 Profile Location:**
   ```
   ~/Library/Application Support/iTerm2/DynamicProfiles/
   └── Connectify.plist
   ```

3. **Conflict Detection:**
   - Read existing profiles from iTerm2
   - Check for name conflicts
   - Warn user and require `--override` flag

4. **Profile Format:**
   iTerm2 uses plist format for DynamicProfiles:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Profiles</key>
       <array>
           <dict>
               <key>Name</key>
               <string>Connectify - Production</string>
               <key>Guid</key>
               <string>connectify-production</string>
               <!-- Color schemes, fonts, etc. -->
           </dict>
       </array>
   </dict>
   </plist>
   ```

**Files to Create/Update:**
- `profiles/` - Directory with bundled profile definitions
- `connectify.py` - Add `profiles` subcommand handler
- `profile_manager.py` - New module for profile management logic
- `README.md` - Document profile management features
- `DEVELOPMENT.md` - Document profile creation process

**Error Handling:**
```bash
# Example: Conflict detected
❌ Profile conflict detected!

The following profiles already exist in iTerm2:
  - Production
  - Development

To install anyway, use:
  connectify profiles install --override

To backup existing profiles first:
  connectify profiles backup
  connectify profiles install --override
```

---

## Completed Features ✅

### Configuration Migration
- ✅ Migrated from `~/.ssh_manager_config.json` to `~/.connectify/hosts.json`
- ✅ Automatic one-time migration
- ✅ Clear user messaging

### Installation Improvements
- ✅ No-sudo installation to `~/.local/bin`
- ✅ Automatic PATH detection and setup
- ✅ Non-interactive installation (works with `curl | sh`)
- ✅ Clear post-installation guidance

### Uninstaller Improvements
- ✅ Non-interactive uninstallation
- ✅ Safe defaults (preserves config)
- ✅ Command-line flags for cleanup options
- ✅ LaunchAgent removal

### Help Menu Cleanup
- ✅ Removed deprecated "ADVANCED UI OPTIONS"
- ✅ Streamlined to show only `connectify ui` subcommands

### Shell Compatibility
- ✅ Fixed `echo -e` → `printf` for POSIX compliance
- ✅ Works with both `sh` and `bash`

---

## Notes

- All features should maintain backward compatibility where possible
- User experience and clear messaging are priorities
- Installation/setup should be as frictionless as possible
- Error messages should be actionable and helpful



