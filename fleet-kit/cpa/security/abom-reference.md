# Osprey Agent Bill of Materials (ABOM) — Proposal

**Date:** 2026-05-18
**Authority:** REVIEW_ONLY
**Source:** Ken Huang, "How to Discover Shadow AI Agents in Your Enterprise" (Substack, May 2026)
**Research:** Perplexity deep analysis of 5-phase framework adapted to single-dev stack

---

## 1. Article Relevance to Osprey

Huang's 5-phase discovery framework was designed for enterprises with thousands of endpoints. Our adaptation for a single-developer AI ops stack is narrower but not simpler:

| Enterprise Concern | Osprey Equivalent |
|-------------------|-------------------|
| Unregistered employee AI agents | Unregistered cron jobs, orphaned MCP servers, zombie processes |
| Cross-team credential sprawl | Collapsed identity — everything runs under one user. One compromise = total |
| Container blind spots | systemd/cron blind spots — scripts launched from timers are invisible to agent inventory |
| LDAP/OAuth correlation | 15 API keys with no workload binding — any agent can use any key |
| SIEM telemetry at scale | Session logs + gateway logs — rich but un-indexed for anomaly patterns |

The framework applies, but the risk profile is inverted: we don't have lateral movement risk, but we have **collapsed identity risk**. If a single API key leaks, there are no compartment boundaries.

---

## 2. Proposed Agent Bill of Materials Schema

Lightweight JSON, versioned in git, one file: `osprey/abom/abom.json`

### Asset Types

```json
{
  "abom_version": "1.0",
  "generated_at": "ISO-8601",
  "assets": {
    "agents": [],
    "mcp_servers": [],
    "api_keys": [],
    "cron_jobs": [],
    "systemd_services": [],
    "log_sinks": [],
    "data_sources": [],
    "config_files": []
  },
  "relationships": [],
  "controls": []
}
```

### Asset Schema (per type)

#### Agent
```json
{
  "asset_id": "agent-spock",
  "type": "agent",
  "name": "Spock (Kirk)",
  "pid": null,
  "runtime": {"host": "spark-5911", "process": "openclaw-gateway", "model": "deepseek-v4-pro"},
  "capabilities": ["tool_calling", "session_spawn", "cron_management", "messaging"],
  "secrets_used": ["key-deepseek"],
  "mcp_servers": ["unusual-whales", "perplexity", "sulu"],
  "network_endpoints": ["api.deepseek.com", "api.telegram.org", "api.openai.com"],
  "trust_level": "bridge_officer",
  "last_seen": "ISO-8601"
}
```

#### API Key
```json
{
  "asset_id": "key-brave-search",
  "type": "api_key",
  "name": "Brave Search API Key",
  "issuer": "brave",
  "storage": {"location": "~/.hermes/secrets/brave_key", "permissions": "600"},
  "bound_to": ["agent-hermes"],
  "scope": ["web.search"],
  "rotated_at": "2026-05-18",
  "duplicated_in": [".openclaw.json", ".claude.json"],
  "risk_notes": ["Found in 254 session logs pre-rotation"],
  "status": "active"
}
```

#### Cron Job
```json
{
  "asset_id": "cron-memory-dreaming",
  "type": "cron_job",
  "name": "Memory Dreaming Promotion",
  "schedule": "0 3 * * *",
  "timezone": "America/Chicago",
  "launches": "agent-main",
  "session_target": "isolated",
  "secrets_used": [],
  "approved": true,
  "pid_registry": null,
  "risk_notes": []
}
```

### Relationship Types
```
agent → uses_secret → api_key
agent → calls → mcp_server
cron_job → launches → agent
agent → writes_to → log_sink
agent → reads_from → data_source
api_key → duplicated_in → config_file
```

---

## 3. Discovery Sources to Inspect

| Source | What It Reveals | Phase |
|--------|----------------|:-----:|
| `openclaw cron list` | Registered cron jobs | 1 |
| `systemctl --user list-timers` | Systemd timers (shadow risk) | 1 |
| `mcporter list` | Active MCP servers | 1 |
| `~/.hermes/secrets/` | Known API keys (secure) | 4 |
| `~/.openclaw/openclaw.json` | Embedded keys, agent config | 1,4 |
| `~/.claude.json` | UW MCP config, duplicated keys | 1,4 |
| `ps aux` | Running processes — any zombie agents? | 5 |
| `~/.hermes/sessions/` | Session logs — key exposure risk | 4 |
| Gateway logs `/tmp/openclaw/openclaw-*.log` | LLM API traffic patterns | 3 |
| `compass.db` | Registered PIDs vs actual running agents | 1,5 |
| `find .env*` across project dirs | Stray .env files, permissions | 1,4 |

---

## 4. Risk Tiers

| Tier | Condition | Response |
|:----:|-----------|----------|
| 🔴 CRITICAL | Active key in world-readable file OR unregistered agent with active credentials OR key found in log file | Will notified immediately. Key rotated within 24h. |
| 🟡 HIGH | Duplicated key across configs OR cron job not in PID registry OR MCP server not in inventory | Flagged in weekly audit. Will decides action. |
| 🟢 MEDIUM | Stale cron job (no runs in 14d) OR agent with overbroad MCP access OR .env with 600 perms but untracked | Report in weekly audit. |
| ⚪ LOW | Config drift (env var vs file) OR agent using expired key OR log retention past policy | Noted. Cleaned up opportunistically. |

---

## 5. Sulu Monitoring Rules

| Rule ID | Trigger | Action |
|---------|---------|--------|
| S-ABOM-01 | New MCP server registered without Compass entry | Forge card: OBSERVATION |
| S-ABOM-02 | API key added outside hermes/secrets/ | Forge card: OBSERVATION |
| S-ABOM-03 | Cron job created without scope packet | Forge card: OBSERVATION |
| S-ABOM-04 | Agent calls MCP server it has never used before | Forge card: OBSERVATION |
| S-ABOM-05 | Key rotation date exceeds 90 days | Forge card: RECOMMENDATION |
| S-ABOM-06 | World-readable .env file detected | Forge card: CRITICAL_OBSERVATION |

All Sulu rules produce Forge cards only — no enforcement, no auto-blocking.

---

## 6. Jekyll Test Cases

| Test ID | Assertion | Failure Mode |
|---------|-----------|-------------|
| J-ABOM-01 | Agent A cannot use Agent B's API key without explicit authorization | Confused deputy |
| J-ABOM-02 | Cron jobs match approved registry | Unauthorized execution |
| J-ABOM-03 | MCP server tool set matches declared scope | Tool creep |
| J-ABOM-04 | Agent output goes only to declared log sinks | Log exfiltration |
| J-ABOM-05 | No process calling LLM API outside registered agents | Shadow agent |
| J-ABOM-06 | Config file permissions: no API key files with perms > 600 | Credential leak |

---

## 7. War Department Response Flow for UNKNOWN Agents

```
DETECT (Sulu/Jekyll/D-018 audit)
  │
  ├─ UNKNOWN agent process detected
  │   ├─ Is it in Compass PID registry? → NO → 🔴 ALERT
  │   ├─ Does it hold active API keys? → YES → 🔴 CRITICAL
  │   └─ What cron/systemd timer launched it? → Trace → Flag
  │
  ├─ UNKNOWN MCP server detected
  │   ├─ Is it registered in mcporter list? → YES → Note, not flag
  │   └─ Is it unregistered? → 🔴 ALERT
  │
  ├─ UNKNOWN API key usage detected
  │   ├─ Key in hermes/secrets/? → YES → Note
  │   └─ Key in plaintext elsewhere? → 🔴 CRITICAL → Rotate
  │
  └─ All findings → Forge card → Will reviews → Decision
```

War Department does NOT auto-remediate. It SURFACES. Will decides.

---

## 8. Recommendation

**CREATE_PROJECT: D-018 is already the home for this.**

The Phase A credential sweep proved the model works. The ABOM schema formalizes it as a persistent asset registry rather than a one-time audit. D-018 Phase A is complete. Phases B (registry audit) and C (traffic baselining) are defined. The ABOM schema in this proposal becomes the data model for all future phases.

**Next Step:** Build the initial ABOM JSON from today's Phase A findings. Populate with all known agents, MCP servers, cron jobs, and API keys. File at `osprey/abom/abom.json`. Run the first full registry cross-reference (Phase B) this Sunday as the inaugural weekly dual audit.

**Risk:** Over-engineering. The ABOM is only useful if maintained. If it drifts, it becomes another dead artifact. The weekly dual audit is the enforcement mechanism — it regenerates the ABOM from live state, not the other way around.
