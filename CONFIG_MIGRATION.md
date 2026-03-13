# Configuration Migration Summary

## Changes Made

### New Configuration Location

**Old Location:** `~/.ssh_manager_config.json`  
**New Location:** `~/.connectify/hosts.json`

### Why This Change?

1. **Better Organization**: All Connectify files in one directory (`~/.connectify/`)
2. **Clearer Naming**: `hosts.json` is more descriptive than `ssh_manager_config.json`
3. **Consistent Structure**: Logs, PID files, and config all in `~/.connectify/`

### Automatic Migration

The application automatically migrates existing configurations:

**Conditions for Migration:**
- Old config exists: `~/.ssh_manager_config.json`
- New config doesn't exist: `~/.connectify/hosts.json`

**Migration Process:**
1. Detects old config file
2. Creates `~/.connectify/` directory
3. Copies config to new location
4. Removes old config file
5. Shows success message

**User Experience:**
```
🔄 Migrating configuration to new location...
   Old: /Users/you/.ssh_manager_config.json
   New: /Users/you/.connectify/hosts.json
✅ Configuration migrated successfully!
   Your hosts are now in: /Users/you/.connectify/hosts.json
```

### Files Updated

**Core Application:**
- ✅ `main.py` - Added `migrate_old_config()` method, updated default paths
- ✅ `api_server.py` - Updated default config path
- ✅ `connectify.py` - No changes needed (uses main.py defaults)

**Installation Scripts:**
- ✅ `install.sh` - Updated config path in post-install message
- ✅ `uninstall.sh` - Updated to handle both old and new config locations

**Documentation:**
- ✅ `README.md` - Updated config file path
- ✅ `main.py` help text - Updated config paths in troubleshooting section

### Backward Compatibility

**For Existing Users:**
- ✅ Automatic one-time migration on first run
- ✅ Old config is safely moved (not copied)
- ✅ Clear messaging about what happened
- ✅ No manual intervention required

**For New Users:**
- ✅ Config created directly in new location
- ✅ No migration needed

### Uninstallation Behavior

The uninstaller now handles both locations:

**Default (preserves config):**
```bash
curl -LsSf https://raw.githubusercontent.com/.../uninstall.sh | sh
```
Shows:
```
ℹ️  Configuration files preserved:
  - ~/.connectify/ (hosts.json, logs, PID files)
  - ~/.ssh_manager_config.json (old config, can be removed)  # if exists

ℹ️  To remove them, run:
  rm -rf ~/.connectify
  rm -f ~/.ssh_manager_config.json  # if exists
```

**With config removal:**
```bash
curl -LsSf https://raw.githubusercontent.com/.../uninstall.sh | sh -s -- --remove-config
```
Removes both old and new config files automatically.

## Testing

Migration was tested successfully:
- ✅ Old config detected
- ✅ New directory created
- ✅ Config copied successfully
- ✅ Old config removed
- ✅ All hosts preserved
- ✅ Application works with new location

## Directory Structure

```
~/.connectify/
├── hosts.json          # SSH host configurations (migrated from ~/.ssh_manager_config.json)
├── ui.log             # UI server logs
└── ui.pid             # UI server PID file
```

## Summary

This migration provides:
- ✅ **Cleaner file organization**
- ✅ **Automatic migration** (no user action needed)
- ✅ **Clear communication** (users know what happened)
- ✅ **Safe operation** (old file removed only after successful migration)
- ✅ **Backward compatible** (handles both old and new locations)
