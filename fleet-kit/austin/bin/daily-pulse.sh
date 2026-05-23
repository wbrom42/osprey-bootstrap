#!/usr/bin/env bash
# Daily health pulse — cron, Jekyll, disk, memory
set -e
echo "=== $(date -Imin) ==="
echo "Cron health:" && openclaw cron list 2>/dev/null | head -5
echo "Disk:" && df -h / | tail -1
echo "Jekyll:" && cd ~/spark-vault/projects/jekyll-agent && bash run-jekyll.sh 2>/dev/null || echo "Jekyll not found"
