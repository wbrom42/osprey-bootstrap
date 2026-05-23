#!/usr/bin/env bash
# Osprey Bootstrap — Stage 1-4 automated installer
# Run on bare Ubuntu 24.04 ARM64
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[BOOTSTRAP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

log "Osprey Bootstrap — Stage 1-4"
echo ""

# Stage 1: System deps
log "Stage 1: System dependencies"
sudo apt update && sudo apt install -y git curl wget build-essential python3 python3-pip python3-venv ca-certificates gnupg jq
log "Stage 1 complete."

# Stage 2: Docker
log "Stage 2: Docker"
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
fi
log "Stage 2 complete."

# Stage 3: Node.js 22
log "Stage 3: Node.js 22"
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt install -y nodejs
fi
log "Node $(node --version)"

# Stage 4: OpenClaw + Ollama
log "Stage 4: OpenClaw + Ollama"
if ! command -v openclaw &>/dev/null; then
  npm install -g openclaw
fi

if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull nomic-embed-text
fi

log "Bootstrap complete. Next: clone spark-vault, configure gateway."
echo ""
echo "  git clone git@github.com:wbrom42/spark-vault.git ~/spark-vault"
echo "  openclaw gateway init"
