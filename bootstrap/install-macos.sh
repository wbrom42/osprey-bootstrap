#!/usr/bin/env bash
# Osprey Bootstrap — macOS (Apple Silicon) installer
# Target: Apple Mini M4 Pro, macOS 15+
# Run from a fresh macOS install
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[BOOTSTRAP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

OSPREY_ROOT="$HOME/spark-vault"
NODE_VERSION="22"

echo "╔══════════════════════════════════════════╗"
echo "║   Osprey Bootstrap — macOS (Apple Silicon) ║"
echo "║   Target: Service Manager Node           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Stage 0: Pre-flight checks ──────────────────────────
log "Stage 0: Pre-flight checks"

ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
  err "This installer is for Apple Silicon (arm64) only."
  err "Detected: $ARCH"
  exit 1
fi

if [ "$(uname)" != "Darwin" ]; then
  err "This installer is for macOS only."
  exit 1
fi

log "Apple Silicon detected — $ARCH"
log "macOS $(sw_vers -productVersion)"

# ── Stage 1: Xcode CLI Tools ─────────────────────────────
log "Stage 1: Xcode Command Line Tools"
if xcode-select -p &>/dev/null; then
  log "Xcode CLI tools already installed."
else
  log "Installing Xcode CLI tools..."
  xcode-select --install
  warn "Complete the GUI installer, then re-run this script."
  exit 0
fi

# ── Stage 2: Homebrew ────────────────────────────────────
log "Stage 2: Homebrew"
if command -v brew &>/dev/null; then
  log "Homebrew already installed: $(brew --version | head -1)"
else
  log "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  
  # Add to PATH for Apple Silicon
  if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
  fi
fi

# ── Stage 3: Core Dependencies ───────────────────────────
log "Stage 3: Core dependencies"

brew install \
  git curl wget \
  python@3.12 \
  node@$NODE_VERSION \
  jq ripgrep fd \
  pandoc weasyprint \
  tmux htop \
  gh

# Link node
brew link --overwrite node@$NODE_VERSION 2>/dev/null || true

log "Node.js: $(node --version)"
log "Python: $(python3 --version)"

# ── Stage 4: Docker Desktop ──────────────────────────────
log "Stage 4: Docker Desktop"
if command -v docker &>/dev/null; then
  log "Docker already installed: $(docker --version)"
else
  log "Installing Docker Desktop..."
  brew install --cask docker
  warn "Open Docker Desktop from Applications to complete setup."
  warn "Then re-run this script to continue."
fi

# ── Stage 5: Ollama ──────────────────────────────────────
log "Stage 5: Ollama"
if command -v ollama &>/dev/null; then
  log "Ollama already installed: $(ollama --version)"
else
  log "Installing Ollama..."
  brew install ollama
  # Start Ollama as background service
  brew services start ollama
fi

log "Pulling nomic-embed-text (274MB)..."
ollama pull nomic-embed-text 2>/dev/null || warn "Ollama not running — pull nomic-embed-text after starting ollama serve"

# ── Stage 6: Node.js Global Packages ─────────────────────
log "Stage 6: Node.js global packages"

npm install -g openclaw

# ── Stage 7: Vault & Workspace ───────────────────────────
log "Stage 7: Workspace setup"

mkdir -p "$OSPREY_ROOT"
mkdir -p "$OSPREY_ROOT/memory"
mkdir -p "$OSPREY_ROOT/handoffs/inbox/real"
mkdir -p "$OSPREY_ROOT/handoffs/traces"
mkdir -p "$OSPREY_ROOT/handoffs/receipts"
mkdir -p "$OSPREY_ROOT/wiki/sources"
mkdir -p "$OSPREY_ROOT/wiki/syntheses"
mkdir -p "$OSPREY_ROOT/wiki/entities"
mkdir -p "$OSPREY_ROOT/wiki/fleet"
mkdir -p "$OSPREY_ROOT/reports"
mkdir -p "$OSPREY_ROOT/projects"
mkdir -p "$OSPREY_ROOT/osprey/doctrine"

log "Workspace created at $OSPREY_ROOT"

# ── Stage 8: Python Dependencies ─────────────────────────
log "Stage 8: Python dependencies"

pip3 install --break-system-packages \
  pyyaml requests python-dotenv \
  sqlite-utils rich typer \
  beautifulsoup4 lxml trafilatura \
  feedparser pdfplumber pypdf \
  rapidfuzz tenacity tqdm networkx \
  pandas numpy scipy matplotlib \
  reportlab weasyprint markdown \
  alpaca-py pytz python-dateutil

log "Python dependencies installed."

# ── Stage 9: Apply Fleet Kit ─────────────────────────────
log "Stage 9: Apply Service Manager fleet kit"

if [ -d "fleet-kit/service-manager" ]; then
  KIT_DIR="fleet-kit/service-manager"
elif [ -d "../fleet-kit/service-manager" ]; then
  KIT_DIR="../fleet-kit/service-manager"
else
  warn "Fleet kit not found in expected location."
  warn "Clone osprey-bootstrap and run from repo root."
  warn "  git clone https://github.com/wbrom42/osprey-bootstrap.git"
  KIT_DIR=""
fi

if [ -n "$KIT_DIR" ]; then
  log "Applying fleet kit from $KIT_DIR"
  
  # Core DNA
  cp "$KIT_DIR/core/"* "$OSPREY_ROOT/" 2>/dev/null && log "  ✅ core/"
  
  # Jekyll
  mkdir -p "$OSPREY_ROOT/projects/jekyll-agent"
  cp "$KIT_DIR/jekyll/"* "$OSPREY_ROOT/projects/jekyll-agent/" 2>/dev/null && log "  ✅ jekyll/"
  
  # Governance
  mkdir -p "$OSPREY_ROOT/projects-office/governance"
  cp "$KIT_DIR/governance/"* "$OSPREY_ROOT/projects-office/governance/" 2>/dev/null && log "  ✅ governance/"
  
  # Trading
  mkdir -p "$OSPREY_ROOT/projects/D-013/build"
  cp -r "$KIT_DIR/trading/"* "$OSPREY_ROOT/projects/D-013/" 2>/dev/null && log "  ✅ trading/"
  
  # Security
  mkdir -p "$OSPREY_ROOT/projects/D-018"
  cp "$KIT_DIR/security/"* "$OSPREY_ROOT/projects/D-018/" 2>/dev/null && log "  ✅ security/"
  
  # Forge
  mkdir -p "$OSPREY_ROOT/projects/improvement-loop"
  cp "$KIT_DIR/forge/"* "$OSPREY_ROOT/projects/improvement-loop/" 2>/dev/null && log "  ✅ forge/"
  
  # Bin
  mkdir -p "$HOME/.local/bin"
  cp "$KIT_DIR/bin/"* "$HOME/.local/bin/" 2>/dev/null && chmod +x "$HOME/.local/bin/"*.sh && log "  ✅ bin/"
  
  # Academy
  mkdir -p "$OSPREY_ROOT/projects/academy"
  cp "$KIT_DIR/academy/"* "$OSPREY_ROOT/projects/academy/" 2>/dev/null && log "  ✅ academy/"
  
  log "Fleet kit applied."
fi

# ── Stage 10: Shell Profile ──────────────────────────────
log "Stage 10: Shell profile"

if ! grep -q "osprey-bootstrap" "$HOME/.zprofile" 2>/dev/null; then
  cat >> "$HOME/.zprofile" << 'PROFILE'

# ── Osprey ──────────────────────────────────────────
export OSPREY_ROOT="$HOME/spark-vault"
export PATH="$HOME/.local/bin:$PATH"
eval "$(/opt/homebrew/bin/brew shellenv)"
PROFILE
  log "Added Osprey config to ~/.zprofile"
fi

# ── Done ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Bootstrap Complete                      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. source ~/.zprofile"
echo "  2. openclaw gateway init"
echo "  3. Configure API keys in ~/.openclaw/secrets/.env"
echo "  4. bash bootstrap/verify-macos.sh"
echo ""
echo "For full instructions: docs/system-rebuild-manual.md"
