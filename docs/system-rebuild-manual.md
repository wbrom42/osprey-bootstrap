# Osprey System Rebuild Manual

**Version:** 1.0  
**Last Updated:** 2026-05-23  
**Purpose:** Complete rebuild of the Osprey system from bare metal using only this vault.

---

## Prerequisites

### Hardware
- ARM64 Linux system (aarch64)
- Minimum 128GB unified RAM
- Minimum 1TB NVMe storage
- NVIDIA Blackwell GPU (for local inference)
- 10GbE or faster networking
- Current host: NVIDIA DGX Spark (spark-5911)

### Software Versions (target)
| Component | Version | Notes |
|-----------|---------|-------|
| Ubuntu | 24.04 LTS | ARM64 build |
| Node.js | 22.x | Via NodeSource or nvm |
| Python | 3.12+ | System python3 |
| Docker | 29.x | Community Edition |
| Ollama | 0.20+ | Local LLM inference |
| OpenClaw | 2026.5.20+ | npm global install |

---

## Stage 1: Base System

### 1.1 OS Installation
Ubuntu 24.04 ARM64 server. Standard install. No GUI needed.

### 1.2 System Dependencies
```bash
sudo apt update && sudo apt install -y \
  git curl wget build-essential \
  python3 python3-pip python3-venv \
  ca-certificates gnupg lsb-release \
  poppler-utils pandoc weasyprint \
  jq fd-find ripgrep \
  vim tmux htop
```

### 1.3 Docker
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo systemctl enable docker
```

### 1.4 Node.js 22
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### 1.5 Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text  # Required for memory search embeddings
```

### 1.6 OpenClaw Gateway
```bash
npm install -g openclaw
openclaw gateway init
systemctl --user enable openclaw-gateway
systemctl --user start openclaw-gateway
```

---

## Stage 2: Vault & Workspace

### 2.1 Clone the Vault
```bash
git clone git@github.com:wbrom42/spark-vault.git ~/spark-vault
cd ~/spark-vault
```

### 2.2 Directory Structure (create if missing)
```bash
mkdir -p ~/spark-vault/memory
mkdir -p ~/spark-vault/handoffs/inbox/real
mkdir -p ~/spark-vault/handoffs/traces
mkdir -p ~/spark-vault/handoffs/receipts
mkdir -p ~/spark-vault/wiki/sources
mkdir -p ~/spark-vault/wiki/syntheses
mkdir -p ~/spark-vault/wiki/entities
mkdir -p ~/spark-vault/wiki/fleet
mkdir -p ~/spark-vault/reports
mkdir -p ~/spark-vault/projects
mkdir -p ~/spark-vault/osprey/doctrine
mkdir -p ~/.hermes/scripts
mkdir -p ~/.hermes/log
mkdir -p ~/.hermes/d015
mkdir -p ~/.hermes_handoff/handoff-queue-hermes
mkdir -p ~/.hermes_handoff/handoff-queue-scock
```

---

## Stage 3: Gateway Configuration

### 3.1 Core Config
The gateway config lives at `~/.openclaw/openclaw.json`. Key sections:

**Channels:**
- Telegram bot (token, DM policy allowlist)
- Slack (optional)

**Model Providers:**
- `deepseek` — primary agent model
- `openai` — GPT-5.4/5.5 fallback
- `anthropic` — OAuth preferred, no API key
- `ollama` — local embeddings (nomic-embed-text)

**Agents:**
- `main` — Spock (primary agent)
- `sulu` — Forge monitor (read-only)

### 3.2 Restore from Backup
If restoring from a previous installation:
```bash
# Restore the config (replace with your backup)
cp /path/to/backup/openclaw.json ~/.openclaw/openclaw.json
openclaw gateway restart
```

### 3.3 Verify Gateway
```bash
openclaw gateway status
# Expected: active, port 18789, loopback
```

---

## Stage 4: MCP Servers

### 4.1 Sulu (Forge Monitor)
Server script: `~/.hermes/scripts/sulu-server.py`
```json
{
  "sulu": {
    "command": "python3",
    "args": ["/home/infinitespark2/.hermes/scripts/sulu-server.py"]
  }
}
```
Requires: `osprey/compass/compass.db` (SQLite)

### 4.2 SQLite Compass
```json
{
  "sqlite-compass": {
    "command": "python3",
    "args": ["/home/infinitespark2/spark-vault/osprey/mcp/sqlite-mcp-launcher.py"],
    "env": {"SQLITE_READONLY": "1"}
  }
}
```

### 4.3 Perplexity
```json
{
  "perplexity": {
    "command": "npx",
    "args": ["-y", "@perplexity-ai/mcp-server"],
    "env": {"PERPLEXITY_API_KEY": "<your-key>"}
  }
}
```

### 4.4 Unusual Whales (external HTTP MCP)
Configured via `openclaw.json` MCP servers section with UW API key.

### 4.5 Verify MCP Servers
```bash
mcporter list
# Expected: sulu, sqlite-compass, perplexity, unusual-whales
```

---

## Stage 5: Plugins

Install via npm in the OpenClaw plugin directory:
```bash
cd ~/.openclaw
npm install @openclaw/codex
npm install @openclaw/discord
npm install @openclaw/brave-plugin
npm install @openclaw/slack
```

Restart gateway after plugin installation:
```bash
openclaw gateway restart
```

---

## Stage 6: Skills

### 6.1 Built-in Skills (shipped with OpenClaw)
Located at `~/.npm-global/lib/node_modules/openclaw/skills/`. 60+ skills including:
- `gemini`, `github`, `slack`, `canvas`, `tmux`, `weather`
- `session-logs`, `skill-creator`, `diagram-maker`, `taskflow`

### 6.2 User Skills (workspace)
```bash
# Located in the vault:
~/spark-vault/skills/         # blacklight, service-fire
~/.openclaw/plugin-skills/    # browser-automation, obsidian-vault-maintainer, wiki-maintainer, decommission
```

### 6.3 Restore Skills
```bash
# If skills directory is missing, skills are in the vault:
ls ~/spark-vault/skills/
ls ~/.openclaw/plugin-skills/
```

---

## Stage 7: Python Dependencies

### 7.1 Core Dependencies
```bash
pip3 install --break-system-packages \
  pyyaml requests python-dotenv \
  sqlite-utils rich typer \
  beautifulsoup4 lxml trafilatura \
  feedparser pdfplumber pypdf \
  rapidfuzz tenacity tqdm networkx \
  pandas numpy scipy matplotlib \
  reportlab weasyprint markdown
```

### 7.2 D-013 Trading Dependencies
```bash
pip3 install --break-system-packages \
  alpaca-py pytz python-dateutil
```

### 7.3 Radar (A-024) Dependencies
```bash
pip3 install --break-system-packages -r ~/spark-vault/projects/A-024/radar/requirements.txt
```

---

## Stage 8: API Keys & Secrets

### 8.1 Environment Files
Each agent needs environment variables for API keys:

**OpenClaw Gateway** (`~/.openclaw/secrets/.env`):
```
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

**Hermes Runtime** (if using Hermes Agent):
```
ANTHROPIC_API_KEY=sk-ant-...  # OAuth preferred
```

### 8.2 Key Locations
| Key | Location | Scope |
|-----|----------|-------|
| DeepSeek API | `~/.openclaw/secrets/.env` or env var | All agents via gateway |
| OpenAI API | `~/.openclaw/secrets/.env` | GPT-5.4/5.5 fallback |
| Anthropic OAuth | `~/.claude/.credentials.json` | Claude models |
| Perplexity API | MCP config in openclaw.json | Research queries |
| UW API | MCP config in openclaw.json | Market data |
| Telegram Bot | openclaw.json channels.telegram.botToken | Messaging |
| X/Twitter Bearer | `projects/A-024/radar/.env` | Signal intake |
| Alpaca Paper | `projects/D-001/build/account3/.alpaca.env` | Paper trading |

### 8.3 Secrets Bootstrap
```bash
# Create secrets directory
mkdir -p ~/.openclaw/secrets

# Template .env file
cat > ~/.openclaw/secrets/.env << 'EOF'
DEEPSEEK_API_KEY=sk-REPLACE_ME
OPENAI_API_KEY=sk-REPLACE_ME
EOF
chmod 600 ~/.openclaw/secrets/.env
```

---

## Stage 9: Cron Jobs

### 9.1 Restore from Backup
Cron jobs are stored in `~/.openclaw/cron/jobs.json`. To restore:
```bash
# Verify cron store exists
openclaw cron list

# Jobs are auto-loaded from jobs.json on gateway start
# If restoring from backup:
cp /path/to/backup/jobs.json ~/.openclaw/cron/jobs.json
openclaw gateway restart
```

### 9.2 Key Crons (91 total)
| Name | Schedule | Purpose |
|------|----------|---------|
| `shadow-swarm-generator` | Every 10m | Security fuzzing |
| `enrichment-cache-build` | Hourly | Market data cache |
| `bottleneck-radar-alerts` | Hourly | Signal scoring |
| `wb-congress-feed` | Daily 10am | Congress trades |
| `wb-morning-diagnostics` | Daily 5:05am | System health |
| `wb-morning-herald` | Daily 5:30am | Morning brief |
| `Jekyll Daily Full Suite` | Daily 6am | Behavioral tests |
| `asian-foundry-ingest` | Daily 6:10am | Supply chain |
| `Macro Clocks` | Weekdays 5am | Macro snapshot |
| `i001-x-feed-daily` | Daily 5pm | X signal intake |
| `Memory Dreaming Promotion` | Daily 3am | Memory review |

### 9.3 Systemd Timers (for script execution)
Crons that need direct script execution (not LLM reasoning) use systemd:
```bash
systemctl --user list-timers | grep -E "wb-|osprey-"
```

---

## Stage 10: Docker Services

### 10.1 Neo4j (D-015 Phase 1)
```bash
docker run -d --name neo4j-osprey \
  -p 7474:7474 -p 7687:7687 \
  -v ~/neo4j/data:/data \
  -v ~/neo4j/logs:/logs \
  -e NEO4J_AUTH=neo4j/osprey2026 \
  neo4j:community
```

### 10.2 Qdrant (D-015 Phase 1)
```bash
docker run -d --name qdrant-osprey \
  -p 6333:6333 -p 6334:6334 \
  -v ~/qdrant/storage:/qdrant/storage \
  qdrant/qdrant
```

### 10.3 Verify Services
```bash
docker ps | grep -E "neo4j|qdrant"
curl http://localhost:7474   # Neo4j browser
curl http://localhost:6333   # Qdrant health
```

---

## Stage 11: Agent Configuration

### 11.1 Main Agent (Spock)
Config section in `openclaw.json`:
```json
{
  "agents": {
    "main": {
      "model": "deepseek/deepseek-v4-pro",
      "workspace": "~/spark-vault",
      "startupFiles": [
        "AGENTS.md", "SOUL.md", "MEMORY.md",
        "OSPREY_CONSTITUTION.md", "OSPREY_OPERATING_MANUAL.md",
        "HEARTBEAT.md", "STARTUP_CONTEXT.md"
      ]
    }
  }
}
```

### 11.2 Sulu Agent
Sulu runs as a session-based agent for Forge monitoring:
```json
{
  "sulu": {
    "model": "deepseek/deepseek-v4-pro",
    "workspace": "~/spark-vault/projects/sulu-agent"
  }
}
```

### 11.3 Fleet Agents (Pre-positioned)
Agent configs exist for fleet nodes in `~/.openclaw/agents/`:
```
osprey-knowledge/  — Wiki reader bot (read-only)
osprey-atlas/      — Wiki writer bot (mention-gated, not deployed)
cpa/               — CPA node agent
service-manager/   — Service Fire operations
```

---

## Stage 12: Hermes Runtime (Optional)

Hermes is a separate agent runtime, not managed by OpenClaw.

### 12.1 Hermes Directory Structure
```
~/.hermes/
  config.yaml           — Hermes config
  cron/jobs.json        — Hermes cron DB (cached view)
  scripts/              — Sulu server, inbox sweep, etc.
  plugins/yantrikdb/    — Memory provider
  skills/               — Hermes-specific skills
  log/                  — Memory log + traces
  yantrikdb-memory.db   — Structured memory DB
```

### 12.2 Hermes-Specific Tools
- `inbox-sweep.py` — Consolidates handoffs from all queues
- `sulu-server.py` — MCP server for Forge/Sulu
- `auto-close-review-gates.py` — 72h auto-approve
- `validate_handoff.py` — Handoff format validator

---

## Stage 13: Fleet Node Deployment

### 13.1 Fleet Kit Location
```
~/spark-vault/projects/osprey-core/build/fleet-kit/dist/
  service-manager/  — Service Fire operations node
  cpa/              — CPA/tax research node
  josh/             — Full fleet node
  austin/           — Full fleet node
```

### 13.2 Deploying a Fleet Node
```bash
# 1. Copy fleet kit to target machine
scp -r ~/spark-vault/projects/osprey-core/build/fleet-kit/dist/<node>/ \
       target:~/.openclaw/

# 2. On target machine — install OpenClaw
npm install -g openclaw
openclaw gateway init

# 3. Apply fleet node config
cp ~/.openclaw/<node>/core/* ~/spark-vault/
cp ~/.openclaw/<node>/jekyll/* ~/spark-vault/projects/jekyll-agent/

# 4. Set up node-specific MEMORY.md
# Each node has its own MEMORY.md with node-specific boundaries

# 5. Register node in fleet wiki
# Add to wiki/fleet/registry.md
```

### 13.3 Fleet Node Startup Sequence
1. Read STARTUP_CONTEXT.md
2. Read OSPREY_CONSTITUTION.md
3. Read HEARTBEAT.md
4. Read MEMORY.md (node-specific)
5. Run fleet pulse scripts
6. Check fleet wiki for father updates
7. Do not act until lane and authority confirmed

---

## Stage 14: Verification

### 14.1 System Health Check
```bash
# Gateway
openclaw gateway status

# Cron health
openclaw cron list | grep error

# MCP servers
mcporter list

# Memory
free -h

# Disk
df -h /

# Docker
docker ps
```

### 14.2 Jekyll Test Suite
```bash
bash ~/spark-vault/projects/jekyll-agent/run-jekyll.sh
# Expected: 13-15 tests passing
# Pre-existing known failures: JH-001 (legacy handoffs), JH-003 (disabled crons)
```

### 14.3 Startup Context Integrity
```bash
python3 ~/spark-vault/projects/jekyll-agent/jh005_startup_context_integrity.py
# Expected: PASS — all pointers resolve
```

### 14.4 Heartbeat Check
```bash
python3 ~/spark-vault/projects/jekyll-agent/jh007_heartbeat_staleness.py
# Expected: PASS — HEARTBEAT.md current
```

### 14.5 Inbox Sweep
```bash
python3 ~/.hermes/scripts/inbox-sweep.py
```

### 14.6 Full Startup Protocol
```bash
# 1. Check HEARTBEAT.md
# 2. Run inbox sweep
# 3. Check cron health
# 4. Check Compass for recent entries
# 5. Report for duty
```

---

## Emergency Procedures

### Gateway Failure
```bash
systemctl --user restart openclaw-gateway
openclaw gateway status
```

### Cron Dispatch Stalls
If jobs show "model-call-started" timeout:
1. Switch model from deepseek-v4-flash to deepseek-v4-pro
2. Increase timeout (300s for complex jobs)
3. Add fallback model (GPT-5.4)

### MCP Server Failure
```bash
# Check running python processes
pgrep -a sulu-server
# Kill duplicates if >1
pkill sulu-server
# Restart gateway to re-init MCP
openclaw gateway restart
```

### Disk Space Recovery
```bash
# Checkpoint pruning (auto-enabled, 30-day retention)
# Clean state snapshots
# Remove old docker images: docker system prune -a
```

---

## Key File Map

| File | Purpose |
|------|---------|
| `STARTUP_CONTEXT.md` | Boot pointer — where to find everything |
| `HEARTBEAT.md` | System health — what's working, what's degraded |
| `MEMORY.md` | Durable memory — decisions, holds, active projects |
| `OSPREY_CONSTITUTION.md` | The law — what we will NOT do |
| `OSPREY_OPERATING_MANUAL.md` | Procedures — how we DO things |
| `SOUL.md` | Persona — who Spock is |
| `AGENTS.md` | Agent rules — applies to all agents |
| `TOOLS.md` | Environment reference — MCP, crons, paths |
| `wiki/syntheses/har-003-infrastructure-as-memory.md` | Project registry |
| `osprey/compass/compass.db` | Lifecycle tags, event store |
| `projects/jekyll-agent/` | Behavioral safety test suite |
| `projects/A-024/radar/` | Signal ingestion pipeline |
| `projects/D-013/` | NeuroTrader trading architecture |
| `projects/osprey-core/build/fleet-kit/` | Fleet node deployment packages |

---

## Appendix A: macOS Bootstrap (Apple Mini M4)

For Service Manager nodes running on Apple Silicon:

### A.1 Differences from Linux
| Concern | Linux (DGX Spark) | macOS (Apple Mini) |
|---------|-------------------|---------------------|
| Package manager | apt | Homebrew (brew) |
| Paths | `/home/infinitespark2/` | `/Users/$USER/` — all paths use `$HOME` |
| Docker | Native | Docker Desktop |
| GPU | NVIDIA Blackwell (CUDA) | Apple Silicon GPU (Metal) |
| Service manager | systemd (systemctl) | launchd (launchctl) |
| Ollama | Native Linux | macOS builds available |
| OpenClaw | npm global install | npm global install (same) |

### A.2 Automated Install
```bash
git clone https://github.com/wbrom42/osprey-bootstrap.git
cd osprey-bootstrap
bash bootstrap/install-macos.sh
```
Covers: Xcode CLI → Homebrew → core deps → Docker → Ollama → OpenClaw → workspace → fleet kit.

### A.3 Verify
```bash
bash bootstrap/verify-macos.sh
```
27 checks: runtime, services, workspace, fleet kit.

### A.4 Manual Steps (not automated)
1. Complete Docker Desktop setup (GUI — first launch)
2. Configure API keys: `~/.openclaw/secrets/.env`
3. Run `openclaw gateway init`
4. Edit STARTUP_CONTEXT.md with correct `$HOME` paths
5. Restore cron jobs: `openclaw cron list` (will populate from config)

### A.5 Path Differences
All fleet kit files use `~/spark-vault/` (relative). On macOS this resolves to `/Users/$USER/spark-vault/`. Update any hardcoded `/home/infinitespark2/` paths if they appear in config files.

### A.6 Known Limitations
- No local 405B-class inference — Apple GPU ≠ NVIDIA CUDA
- Docker Desktop has higher resource overhead than native Linux Docker
- Neo4j/Qdrant via Docker Desktop work but with slightly higher latency
- systemd timers unavailable — use OpenClaw cron exclusively
