# Obsidian Vault Integration

## Status: ⚠️ Partial (Permission Issue)

### What's Working
- ✅ obsidian-cli configured with default vault: `My Brain`
- ✅ Symlink created: `~/vaults/obsidian` → iCloud vault

### The Issue
macOS blocks access to iCloud Drive folders (`~/Library/Mobile Documents/...`) from terminal apps without explicit permission.

**Error:** `operation not permitted` on iCloud vault path

### Solutions

#### Option 1: Grant Terminal Full Disk Access (Easiest)
1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and add your terminal app (Terminal.app or iTerm)
3. Restart terminal
4. Test: `obsidian-cli search "project"`

#### Option 2: Move Vault Out of iCloud (Recommended for Automation)
1. In Obsidian: **Settings** → **About** → **Move vault**
2. Move to `~/Documents/Obsidian/My Brain` (local, not iCloud)
3. Update default: `obsidian-cli set-default "~/Documents/Obsidian/My Brain"`

#### Option 3: Use Obsidian Sync Instead of iCloud
- Keep vault local
- Use Obsidian's built-in sync (paid feature)
- Full automation access without permission issues

### Current Workaround
Until permissions are fixed:
- obsidian-cli works for vaults in `~/Documents/` (non-iCloud)
- Direct file access via symlink works for some operations
- iCloud vault requires manual GUI access

### Test Commands (after fixing permissions)
```bash
# Search note titles
obsidian-cli search "project"

# Search inside notes
obsidian-cli search-content "meeting"

# Create note
obsidian-cli create "Inbox/Idea" --content "My idea here"

# List recent
ls -la ~/vaults/obsidian/
```
