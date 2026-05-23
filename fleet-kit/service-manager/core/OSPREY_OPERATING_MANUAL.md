# OSPREY OPERATING MANUAL

**Procedures — How This System DOES Things**
**Ratified:** 2026-05-20 | **Authority:** Will B. | **Applies to:** Main agent session

---

## §1 — Morning Report for Duty (o7 Protocol)

When Will opens with "o7", the agent reports for duty. This is not a status check — it is identity and context re-establishment.

### Phase 1 — Load Identity

Agent memory is an INDEX, not a warehouse. MEMORY.md and daily logs contain standing direction and pointers to the full data elsewhere (project charters, Compass, HAR-003, Event Store). The morning ritual proves the agent visited all the right places.

1. **Startup Context** — Read `STARTUP_CONTEXT.md`. The pointer map for this session.
2. **Constitution** — Read `OSPREY_CONSTITUTION.md`. What we will NOT do.
3. **Soul** — Read `SOUL.md`. Who I am, how I reason, what I refuse.
4. **Memory** — Read `MEMORY.md`. Standing holds, execution posture, active project index.
5. **Yesterday** — Read `memory/YYYY-MM-DD.md`. What happened, what's open.
6. **Projects** — Read HAR-003 wiki. What's OPERATIONAL, what's parked, what's blocked.
7. **Supersessions** — Read `supersession-registry.md`. Old claims that no longer govern.
8. **Protocols** — Handoff format, EC pipeline, lane boundaries, notification queues.

### Phase 2 — System Pulse

1. **Consolidate inbox** — `python3 ~/.hermes/scripts/inbox-sweep.py`
2. **Cron health** — `openclaw cron list | grep error`
3. **Heartbeat diagnostics** — Check HEARTBEAT.md: errors, memory, disk, gateway, OAuth
4. **Compass** — Recent entries for schedules and plans
5. **Jekyll** — Last run status (JH-002 staleness check)
6. **QM sync** — Check Hermes's queue for pending handoffs, verify Spock→Hermes flags delivered

### Phase 3 — Report for Duty

The report IS the proof. If it's in the brief, the agent visited it.

- **Identity confirmed:** Agent name, role, model
- **Constitution loaded:** Standing holds active
- **Memory loaded:** Yesterday's context, open items
- **Projects active:** Current workstreams, blocked items, parked projects
- **System health:** GREEN / YELLOW / HOLD
- **Agents aligned:** Hermes sync status, pending handoffs
- **Ready for work:** Yes / No (and why)

### Phase 4 — Await Delegation

- **Do NOT start work automatically**
- If no active task: "Science station clear. Awaiting delegation."
- If active task from previous session: present status and await continue order

---

## §2 — EC Academy 5-Step Operating Cycle

Before ANY work begins:

### Step 1 — Classify
Identify the problem architecture:
- **Coding Harness** — Single agent + toolbelt, human quality gate
- **Dark Factory** — Spec in → software out, automated validation
- **Orchestration Framework** — Multi-agent coordination with human judgment gate
- **Diagnostic Pipeline** — Data in → analysis out, scoring function quality gate

### Step 2 — Scope
Write a scope packet with:
- `project_id`, `objective`, `authority_tier`, `risk_tier`
- `allowed_paths`, `forbidden_actions`
- `ec_classification` (architecture + quality_gate + system_maturity)
- `ec_build_order` (data → org → observability → authority)

### Step 3 — Pre-Mortem
Identify failure modes BEFORE execution:
- What could go wrong?
- Likelihood and impact
- Mitigation for each

### Step 4 — Judge
Gate verdict:
- Is this well-scoped?
- Does authority match risk?
- Is there a human in the loop where needed?
- Verdict: APPROVE / APPROVE_WITH_CONDITIONS / REJECT

### Step 5 — Gate
- Run `provenance_gate.py --enforce --handoff <path>`
- All 5 EC steps must PASS
- Log result to Event Store
- Tag in Compass

**Rule:** Run the pipeline. Do NOT write markdown protocol artifacts. The protocol IS the pipeline output.

### OpenClaw Maintenance Doctrine

**SOP:** `osprey/doctrine/openclaw-update-sop.md` (ratified 2026-05-21, Will-approved)
**Clean Reinstall Runbook:** `academy/runbooks/openclaw-clean-reinstall.md` (imported from Jeff Hunter, github.com/jeffjhunter/openclaw-2026.5-update-reinstall)

**Core Rule:** No agent touches the gateway (update, restart, stop, standby) without explicit Will approval. This is doctrine.

**Two Lanes:**
- Lane A: `openclaw update --channel stable` — for routine version bumps with Will approval + full preservation backup
- Lane B: Clean reinstall per Jeff Hunter runbook — when 2+ symptoms of layered upgrade cruft

**Pre-upgrade backup is mandatory** (§4 of SOP). Post-upgrade verification includes version check, gateway status, cron health, model smoke test, doctor clean, and plugin convergence check.

---

## §3 — Handoff Protocol

### Writing a Handoff

1. Generate template: `python3 osprey/enforcement/validate_handoff.py --template --from <agent> --to <agent> --objective "..."`
2. Fill required fields: `handoff_id`, `from_agent`, `to_agent`, `authority`, `objective`
3. Fill context fields: `summary`, `scope_packet`, `references`, `verdict`
4. Validate: `python3 osprey/enforcement/validate_handoff.py --handoff <file>.json`
5. Write to `handoffs/inbox/real/` only if validation passes
6. Drop notification flag in recipient's queue:
   - Hermes → Spock: `~/.hermes/handoff-queue-scock/`
   - Spock → Hermes: `~/.hermes/handoff-queue/`

### Handoff Format

**All handoffs must be JSON.** Markdown handoffs are rejected by QM and flagged by JH-001.

Required fields: `handoff_id`, `from_agent`, `to_agent`, `authority`, `objective`.

### Communication Tags

| Tag | Meaning | Response SLA |
|-----|---------|:-----------:|
| `[BLOCKER]` | Stop work, respond now | 1 hour |
| `[REVIEW]` | Needs review before proceeding | 24 hours |
| `[DELAY]` | Non-blocking issue | 24 hours |
| `[INFO]` | FYI, no response needed | Weekly |
| `[FOLLOWUP]` | Check back on this | Per message |

### Auto-Close Review Gates

Scope packets with `gate_review_tier: auto_close_72h` auto-approve after 72h of no objections.
Applies ONLY to two-way door work (registry conventions, documentation, formatting).
To block: set `packet_status` to REJECTED. To extend: add `approval_extension` field (max one, total 144h).

---

## §4 — Session Closeout (Adios Protocol)

When Will signs off:

1. **Gather** — All handoffs, scope packets, traces, receipts, Forge cards, briefs from current session
2. **Officialize** — Cross-reference against receipt chain. Items without full chain → Forge, not completed.
3. **Cross-agent sync** — Confirm Hermes saw all handoffs. Check notification queues are clean.
4. **Memory drift check** — Did any doctrine change during session? Update supersession registry if needed.
5. **HBO registry** — Did any cron change lane? Note in heartbeat registry.
6. **File trace** — Closeout summary to `projects/H-007/traces/HH-YYYYMMDD-session-closeout.md`
7. **Feed the Forge** — Pending items → Forge cards with priority classification
8. **Update daily memory** — `memory/YYYY-MM-DD.md`
9. **Update STARTUP_CONTEXT.md** — If any pointer changed (new doctrine, new supersession), refresh `last_reviewed` date

Priority classifications:
- **P0** CRITICAL — Security, account blocked, data leak. Immediate.
- **P1** HIGH — Cron broken, pipeline down. 24h.
- **P2** MEDIUM — Performance, design gaps. This week.
- **P3** LOW — Documentation, cleanup. When possible.

---

## §5 — Agent Shakedown (T1-T2-T3)

Every new agent runs three progressive tests:

```
TIER 1 — STATIC (no stakes)
  Controlled scenario, known answer. Tests comprehension of SOUL/AGENTS.
     ↓
TIER 2 — LIVE HISTORICAL (low stakes)
  Historical event, outcome hidden. Grade against known truth.
     ↓
TIER 3 — FORWARD LIVE (real stakes, small)
  Real task, real uncertainty, small blast radius.
```

- Every shakedown produces a grading document
- Failure → revise → re-run → pass or decommission
- 3 strikes same tier = rebuild
- Cadence: T1 within 24h, T2 within 7d, T3 within 30d (new agents). Quarterly re-shakedown (operational).

---

## §6 — Archive Checklist

When a project is archived or an agent is deleted:

- [ ] Disable associated cron jobs (OpenClaw + systemd)
- [ ] Remove associated environment variables / secrets
- [ ] Update HAR-003 project registry
- [ ] Move project files to `projects/archived/`
- [ ] Clean notification queues of stale flags
- [ ] Tag Compass with archive event
- [ ] Verify no other component references the archived paths

---

## §8 — AMFMP File Audit (Monthly)

Per AMFMP-001, every managed file gets a monthly review for drift, staleness, and supersessions.

### Monthly audit checklist:

1. **Grandfather test** — Load an older MEMORY.md or AGENTS.md snapshot. Does the current startup path still resolve correctly? Are there claims in old memory that the supersession registry hasn't marked?
2. **HEARTBEAT.md** — HBO review: status CURRENT, monitored files/agents accurate, known_degraded list updated
3. **STARTUP_CONTEXT.md** — Do all pointers resolve to existing files? Any new doctrine not yet referenced?
4. **Supersession Registry** — Any new drift detected since last audit? File supersession records.
5. **MEMORY.md** — Standing holds still current? Execution posture accurate? Active projects list matches HAR-003?
6. **AGENTS.md** — Under 12,000 bytes? Wired to Constitution and Operating Manual? Role-switching guide current?
7. **SOUL.md** — Core principles still accurate? Any new role boundaries to add?
8. **HBO Registry** — All crons classified Lane A or B? Any changed since last audit?
9. **Wiki (HAR-003)** — Syntheses count, staleness (JH-002), new gaps
10. **Beever Atlas (D-015)** — Ingestion active? Graph fresh? Auto-wiki generating? Every ingested item has `memory_item_id`, `source_surface`, `source_message_id`, `source_author`, `source_timestamp`, `status`, `evidence_path`?
11. **Neo4j/Weaviate projection check** — Do graph/vector results match source evidence? Any projection being used as authority?
12. **Compass source-fidelity audit** — Are Compass entries traceable to reviewed sources? Any unreviewed entries used as doctrine?

**Output:** Single AMFMP audit memo → Hermes for coordination → Will if action needed.

### AMFMP Status Table

After each audit, update the canonical status table:

```
file_id   | file                  | owner  | status       | last_reviewed | startup_load_allowed
AMF-001   | IDENTITY.md           | Spock  | CURRENT      | YYYY-MM-DD    | yes
AMF-002   | SOUL.md               | Spock  | CURRENT      | YYYY-MM-DD    | yes
AMF-004   | AGENTS.md             | Spock  | CURRENT      | YYYY-MM-DD    | yes
AMF-006   | MEMORY.md             | Spock  | CURRENT      | YYYY-MM-DD    | yes
HBO-001   | HEARTBEAT.md          | HBO    | CURRENT      | YYYY-MM-DD    | yes
AMF-C01   | STARTUP_CONTEXT.md    | Spock  | CURRENT      | YYYY-MM-DD    | yes
AMF-C02   | supersession-registry | Spock  | CURRENT      | YYYY-MM-DD    | yes
```

Any file with `startup_load_allowed: no` must not be loaded as current authority.

---

## §7 — Project Initiation Protocol

When Will says "Make it a project" (or any variant):

### You do NOT need to know the PID. The agent classifies and assigns it.

| Domain | PID Prefix | Default Agent | Lane | EC Architecture |
|--------|:---:|:---:|:---:|------|
| Architecture / Doctrine | `A-` | Spock | Lane A | Diagnostic Pipeline |
| Science / Research | `S-` | Spock | Lane A | Diagnostic Pipeline |
| Academy / Training | `ACA-` | Spock | Lane A | Diagnostic Pipeline |
| Deep Research | `DRP-` | Spock | Lane A | Diagnostic Pipeline |
| Monitor / Observe | `M-` | Spock | Lane A | Diagnostic Pipeline |
| Development / Data | `D-` | Hermes | Lane A→B | Coding Harness |
| Hermes / Operations | `H-` | Hermes | Lane B | Orchestration |
| Service Fire | `SF-` | Hermes | Lane B | Orchestration |
| Rogue Fireworks | `RFW-` | Hermes | Lane B | Orchestration |

### Initiation sequence (automatic):

1. **Classify domain** from the task description → assign PID prefix
2. **Assign next number** — query Compass for highest existing number in prefix
3. **Create charter** at `projects/<PID>/CHARTER.md` from domain template
4. **Route to agent** — Spock (research/analysis) or Hermes (build/execute)
5. **Classify EC architecture** — match to domain default
6. **Enter EC pipeline** at Step 1 (classify)
7. **Notify Will** — "Project <PID> created. Charter at <path>. EC pipeline queued."
7. **Notify Hermes** if routed to him

### What Will says vs what happens:

| Will says | System does |
|-----------|------------|
| "Make it a project: study why our reports flood" | → ACA-XXX, Spock, Diagnostic Pipeline |
| "Make it a project: build the closeout gate script" | → H-XXX, Hermes, Orchestration |
| "Make it a project: research Flurit's new release" | → DRP-XXX, Spock, Diagnostic Pipeline |
| "Make it a project: add trading signals for NVDA" | → D-XXX, Hermes, Coding Harness |
| "Make it a project: fix Service Fire invoicing" | → SF-XXX, Hermes, Orchestration |

### Lane gate:
- If Lane B (build/execute/mutate) → agent presents scope for Will approval BEFORE execution
- If Lane A (research/analyze) → agent proceeds, presents findings when done

---

## §9 — Cron Registry

**Who handles the crons.** Every cron job has an explicit owner. No orphan crons.

### Ownership Rules

| Owner | Responsibility | Scope |
|-------|:------------:|-------|
| **Spock** (main) | System monitoring, intelligence feeds, diagnostics | Lane A observability, morning briefings, radar, watchdog, wiki pipeline |
| **Hermes** | Operations, build, data pipelines | Lane B execution, D-xxx projects, cache management, enrichment builds |
| **Sulu** | Forge lifecycle only | `sulu-forge-cycle` — read-only cross-project pattern analysis |
| **Unassigned** (`-`) | Must be assigned within 7d | New crons default here. No cron stays unassigned >7 days. |

### Owner Assignment Protocol

1. New cron created → defaults to creator's agent_id
2. Unassigned crons → Spock reviews weekly (Monday 8am), proposes owner to Will
3. Cron without active owner >7 days → flagged in JH-003, escalated to Will
4. Agent decommissioned → crons reassigned by Spock before agent deletion (§6)

### Active Cron Fleet

Status: `ok` = healthy, `error` = last run failed, `idle` = awaiting first run, `disabled` = intentionally off

#### Spock (Main Agent) — Lane A Observability

| Job Name | Schedule | Status | Notes |
|----------|----------|:------:|-------|
| `shadow-swarm-generator` | every 10m | ok | Jekyll adversarial test generation |
| `enrichment-cache-build` | hourly | ok | Signal enrichment pipeline |
| `bottleneck-radar-alerting` | every 1h | ok | A-024 bottleneck detection |
| `handoff-inbox-monitor` | every 1h | ok | Inbox sweep for pending handoffs |
| `d016-compliance-monitor` | daily 07:30 | ok | D-016 compliance checks |
| `youtube-podcast-pipeline` | daily 08:00 | ok | Podcast ingestion |
| `cron-watchdog` | every 4h | ok | Self-monitoring: cron fleet health |
| `wiki-har-pipeline` | daily 09:00 | **error** | HAR-003 wiki synthesis pipeline |
| `i001-x-feed-daily` | daily 17:00 | ok | I-001 X/Twitter signal feed |
| `d011-ipo-x-feed-daily` | daily 18:00 | ok | D-011 IPO Watch X-feed |
| `a003-harness-x-feed-daily` | daily 18:30 | ok | A-003 Harness Engineering X-feed |
| `Macro Clocks — daily snapshot` | weekdays 05:00 | ok | Macro yield curve/rates snapshot |
| `guardian-daily-vuln-detect` | daily 06:00 | **error** | Security vulnerability scan |
| `bottleneck-radar-friday-brief` | Friday 17:00 | ok | A-024 weekly bottleneck brief |
| `weekly-cost-review` | Sunday 20:00 | ok | Weekly cost/usage review |
| `osv-scanner-weekly` | Monday 06:00 | idle | OSV vulnerability scanner |
| `wb-security-maintenance` | Monday 07:00 | idle | Weekly security maintenance |
| `bottleneck-radar-weekly-review` | Monday 07:00 | idle | A-024 weekly review |
| `opportunity-radar-weekly` | Monday 08:00 | ok | Weekly opportunity radar |
| `macro-forecast-score-001` | May 13 15:30 | ok | Macro forecast scoring (one-shot) |
| `gauntlet-5d-check` | May 15 17:30 | ok | Gauntlet 5-day check (one-shot) |

#### Unassigned — Needs Owner

| Job Name | Schedule | Status | Suggested Owner | Notes |
|----------|----------|:------:|:---------------:|-------|
| `wb-uw-trader-cycle` | daily 08:00 | ok | Hermes | UW trader morning cycle |
| `wb-insider-cache-refresh` | every 4h | ok | Hermes | Insider transaction cache |
| `wb-uw-digest-intraday` | daily 09:00 | ok | Hermes | UW intraday digest |
| `wb-congress-feed` | daily 10:00 | ok | Hermes | Congressional trade feed |
| `wb-uw-trader-daily-summary` | daily 14:45 | ok | Hermes | UW trader EOD summary |
| `wb-compass-compact` | daily 02:00 | ok | Hermes | Compass DB compaction |
| `Memory Dreaming Promotion` | daily 03:00 | ok | Hermes | Memory dreaming to promotion |
| `wb-morning-diagnostics` | daily 05:05 | ok | Hermes | Morning system diagnostics |
| `wb-morning-herald` | daily 05:30 | ok | Hermes | Morning herald briefing |
| `Jekyll Daily Full Suite` | daily 06:00 | ok | Spock | Jekyll safety test suite |
| `asian-foundry-ingest` | daily 06:10 | ok | Hermes | Asian market data ingest |
| `wb-uw-triage-weekly` | Saturday 09:00 | ok | Hermes | UW weekly triage |
| `service-fire-steel-check` | monthly 1st 07:00 | idle | Hermes | Service Fire monthly check |

#### Sulu — Forge Only

| Job Name | Schedule | Status | Notes |
|----------|----------|:------:|-------|
| `sulu-forge-cycle` | every 4h | **error** | Cross-project pattern analysis → Forge cards. Known timeout issue. |

#### Systemd Timers (Non-OpenClaw)

| Timer | Owner | Schedule | Status | Project |
|-------|:-----:|----------|:------:|---------|
| `wb-gmgn-cache.timer` | Hermes | hourly :58 | active | D-002 GMGN cache poller |

### Error Resolution Protocol

1. Cron shows `error` → owner investigates within 4h (business hours) or next startup
2. 3 consecutive errors → auto-escalated to Spock for triage
3. 5 consecutive errors → flagged to Will with root cause analysis
4. All errors logged to Event Store with resolution trace

### Health Check

```bash
# Full fleet status
openclaw cron list

# Errors only
openclaw cron list | grep -i error

# Systemd timers
systemctl --user list-timers

# JH-003 cron health (disabled >24h, errors)
python3 ~/spark-vault/projects/jekyll-agent/jh003_cron_health.py
```

**Last reviewed:** 2026-05-21 | **Next review:** 2026-05-28
