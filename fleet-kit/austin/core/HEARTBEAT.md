# HEARTBEAT — System Health Status

```yaml
hbo_managed: true
program: AMFMP
file_id: HBO-001
file_role: heartbeat_freshness_and_liveness
owner: HBO
domain: War Department / Health
lane: Lane A
authority: DETECT_REPORT_ONLY
status: CURRENT
last_reviewed: 2026-05-20
next_review: 2026-05-27
stale_after: 7d
last_success: 2026-05-23T01:55
last_failure: null
known_degraded: [sulu-forge-cycle (timeout), macro-clocks (timeout)]
monitored_files: [MEMORY.md, AGENTS.md, HAR-003, STARTUP_CONTEXT.md]
monitored_agents: [main, sulu]
monitored_nodes: [spark-5911]
monitored_services: [yantrikdb (hermes memory provider, embedded, ~/.hermes/yantrikdb-memory.db)]
known_degraded: []
failure_route: Quartermaster
evidence_path: openclaw cron list, systemctl, free, df
forbidden_actions:
  - route
  - dispatch
  - approve
  - fix
  - mutate
  - restart_services
  - change_timers
  - change_config
  - promote_memory
  - mutate_compass
  - deploy
  - trade
```

**Check on every heartbeat: run `openclaw cron list | grep error`**

## Current Health (live checks — run now)

```bash
# Cron health: any errors?
openclaw cron list 2>&1 | grep -c "error"

# GMGN cache: systemd timer running?
systemctl --user is-active wb-gmgn-cache.timer

# Memory: below 90%?
free -h | awk 'NR==2{print $3/$2*100}' | awk '{if ($1>90) print "WARN:" $1 "%"; else print "OK:" $1 "%"}'

# Disk: below 90%?
df -h / | awk 'NR==2{print $5}' | sed 's/%//' | awk '{if ($1>90) print "WARN:" $1 "%"; else print "OK:" $1 "%"}'

# Gateway: running?
systemctl --user is-active openclaw-gateway

# API keys: test Anthropic OAuth
grep -q "sk-ant" ~/.claude/.credentials.json && echo "OK: OAuth token exists" || echo "WARN: no OAuth token"

# Jekyll: last run passed?
python3 ~/spark-vault/projects/jekyll-agent/jh002_har003_staleness.py 2>&1 | grep -q "PASS" && echo "OK: HAR-003 current" || echo "WARN: HAR-003 stale"
```

## Active System Checks

| Component | What to check | Cadence |
|-----------|--------------|---------|
| GMGN cache | `systemctl --user is-active wb-gmgn-cache.timer` | Daily |
| Jekyll safety | `bash run-jekyll.sh` (automated at 6am) | Daily |
| Cron errors | `openclaw cron list \| grep error` | Every heartbeat |
| Memory pressure | `free -h` | Every heartbeat |
| Disk pressure | `df -h /` | Every heartbeat |
| Gateway uptime | `openclaw gateway status` | Every heartbeat |
| Anthropic OAuth | Check `~/.claude/.credentials.json` expiry | Weekly |
| AGENTS.md size | <12,000 bytes or cron contexts truncate | Every session |
| YantrikDB health | `hermes memory status` — provider available, no circuit breaker trip | Every heartbeat |

<!-- Hermes closeout last_success: 2026-05-21 22:49 CDT — closeout/startup/handoff flow validated; Sulu MCP Forge card filed; daily memory saved. -->

<!-- Hermes closeout last_success: 2026-05-21 22:49 CDT — closeout/startup/handoff flow validated; Sulu MCP Forge card filed; daily memory saved. -->
