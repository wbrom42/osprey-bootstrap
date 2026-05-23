#!/usr/bin/env bash
# Osprey Verify — macOS post-install health check
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
check() {
  local desc="$1" cmd="$2"
  if eval "$cmd" &>/dev/null; then
    echo -e "  ${GREEN}✅${NC} $desc"
    return 0
  else
    echo -e "  ${RED}❌${NC} $desc"
    FAIL=$((FAIL+1))
    return 1
  fi
}

echo "╔══════════════════════════════════════════╗"
echo "║   Osprey System Verification — macOS     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

FAIL=0

echo "── Core Runtime ──"
check "Xcode CLI Tools" "xcode-select -p"
check "Homebrew" "brew --version"
check "Node.js 22" "node --version | grep 'v22'"
check "Python 3.12" "python3 --version | grep '3.12'"
check "Git" "git --version"
check "jq" "jq --version"
check "pandoc" "pandoc --version"

echo ""
echo "── Services ──"
check "Docker" "docker --version"
check "Ollama" "ollama --version"
check "nomic-embed-text" "ollama list | grep nomic-embed"
check "OpenClaw" "openclaw version"

echo ""
echo "── Workspace ──"
OSPREY_ROOT="$HOME/spark-vault"
check "spark-vault dir" "test -d $OSPREY_ROOT"
check "STARTUP_CONTEXT.md" "test -f $OSPREY_ROOT/STARTUP_CONTEXT.md"
check "HEARTBEAT.md" "test -f $OSPREY_ROOT/HEARTBEAT.md"
check "MEMORY.md" "test -f $OSPREY_ROOT/MEMORY.md"
check "OSPREY_CONSTITUTION.md" "test -f $OSPREY_ROOT/OSPREY_CONSTITUTION.md"
check "Jekyll suite" "test -f $OSPREY_ROOT/projects/jekyll-agent/run-jekyll.sh"
check "Trading pipeline" "test -f $OSPREY_ROOT/projects/D-013/pipeline.py"
check "Inbox dir" "test -d $OSPREY_ROOT/handoffs/inbox/real"
check "Wiki dir" "test -d $OSPREY_ROOT/wiki/syntheses"

echo ""
echo "── Fleet Kit ──"
check "Core DNA" "test -f $OSPREY_ROOT/AGENTS.md && test -f $OSPREY_ROOT/SOUL.md"
check "Governance" "test -d $OSPREY_ROOT/projects-office/governance"
check "Security" "test -d $OSPREY_ROOT/projects/D-018"
check "Forge" "ls $OSPREY_ROOT/projects/improvement-loop/gate_runner.py 2>/dev/null"
check "Bin scripts" "ls $HOME/.local/bin/daily-pulse.sh 2>/dev/null"

TOTAL=27
PASSED=$((TOTAL - FAIL))

echo ""
echo "═══════════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
  echo -e "  ${GREEN}All $TOTAL checks passed ✅${NC}"
else
  echo -e "  ${YELLOW}$PASSED/$TOTAL passed, $FAIL failed${NC}"
  echo ""
  echo "  Fix:"
  [ $FAIL -gt 0 ] && echo "  • Run bootstrap/install-macos.sh for missing dependencies"
  echo "  • Run 'openclaw gateway init' if OpenClaw isn't configured"
fi
echo "═══════════════════════════════════════════"
