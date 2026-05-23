#!/usr/bin/env bash
# Osprey Verify — post-install health check
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
check() {
  if eval "$2" &>/dev/null; then
    echo -e "  ${GREEN}✅${NC} $1"
  else
    echo -e "  ${RED}❌${NC} $1"
    FAIL=$((FAIL+1))
  fi
}

echo "Osprey System Verification"
echo "=========================="
FAIL=0

check "Node.js" "node --version"
check "Python 3" "python3 --version"
check "Docker" "docker --version"
check "Ollama" "ollama --version"
check "OpenClaw" "openclaw gateway status"
check "Git" "git --version"
check "nomic-embed-text" "ollama list | grep nomic-embed"
echo ""
echo "Verification: $((7-FAIL))/7 passed"
if [ $FAIL -gt 0 ]; then
  echo "Run bootstrap/install.sh for missing components."
fi
