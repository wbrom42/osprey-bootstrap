#!/bin/bash
# Weekly Credential Sweep — find exposed API keys
# Run: bash credential-sweep.sh

echo "=== Credential Sweep $(date) ==="
echo ""

# Scan for .env files with world-readable permissions
echo "### World-readable .env files"
find ~/spark-vault -maxdepth 5 -name ".env*" -not -path "*/.venv/*" -not -path "*/node_modules/*" -not -name "*.example" 2>/dev/null | while read f; do
    perms=$(stat -c "%a" "$f" 2>/dev/null)
    if [ "$perms" != "600" ]; then
        echo "  ⚠️  $f ($perms — should be 600)"
    fi
done

# Scan for API key patterns in session logs (count only)
echo ""
echo "### Session log key exposure"
LOG_DIR="$HOME/.hermes/sessions"
if [ -d "$LOG_DIR" ]; then
    COUNT=$(grep -rl "sk-\|api_key\|apiKey.*[A-Za-z0-9]\{20,\}" "$LOG_DIR" 2>/dev/null | wc -l)
    echo "  Files with possible key exposure: $COUNT"
fi

echo ""
echo "### API key inventory"
SECRETS_DIR="$HOME/.hermes/secrets"
if [ -d "$SECRETS_DIR" ]; then
    for keyfile in "$SECRETS_DIR"/*; do
        name=$(basename "$keyfile")
        perms=$(stat -c "%a" "$keyfile")
        echo "  ✅ $name ($perms)"
    done
fi

echo ""
echo "Done."
