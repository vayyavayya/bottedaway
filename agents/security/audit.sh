#!/bin/bash
# Nightly Security Audit Runner
# Executed by clawsec agent via cron

echo "🔒 Security Audit - $(date)"
echo "=========================="

# Check credential file permissions
echo "Checking credential file permissions..."
find ~/.config -type f -exec ls -la {} \; 2>/dev/null | grep -v "drwx" | head -20

# Check for exposed secrets in recent commits
echo ""
echo "Checking recent commits for secrets..."
cd ~/.openclaw/workspace
git log --oneline -10

# Check for files with dangerous permissions
echo ""
echo "Files with 777 permissions:"
find . -type f -perm 777 2>/dev/null | head -10

# Check workspace for common secret patterns
echo ""
echo "Scanning for potential secrets in code..."
grep -r "api_key\|apikey\|secret_key\|password" --include="*.py" --include="*.js" --include="*.sh" . 2>/dev/null | grep -v ".pyc" | head -10

echo ""
echo "=========================="
echo "✅ Audit complete"
