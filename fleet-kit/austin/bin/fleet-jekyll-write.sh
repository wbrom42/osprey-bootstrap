#!/usr/bin/env bash
# Fleet Jekyll Write — pushes test results to shared wiki
INSTANCE="${1:?instance required}"
RESULT_DIR="$HOME/spark-vault/projects/jekyll-agent/test-results"
SHARED="$HOME/spark-vault/wiki/fleet/jekyll"
mkdir -p "$SHARED"

# Run Jekyll and capture results
cd "$HOME/spark-vault/projects/jekyll-agent"
SUMMARY=$(bash run-jekyll.sh 2>&1 | tail -20)

# Write to shared wiki
REPORT="$SHARED/$(date +%Y-%m-%d)-${INSTANCE}-jekyll.md"
{
    echo "# Jekyll Results — $INSTANCE — $(date -I)"
    echo ""
    echo '```'
    echo "$SUMMARY"
    echo '```'
} > "$REPORT"
echo "JEKYLL: $INSTANCE → $REPORT"
