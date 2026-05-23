# AMFMP-001 — Agent Memory File Management Program

**Subtitle:** Keeping OpenClaw from waking up inside an old version of itself  
**Status:** DRAFT_DOCTRINE  
**Domain:** Osprey Core / War Department  
**Lane:** Lane A doctrine  
**Authority:** REVIEW_ONLY  
**Execution authority:** None  
**System mutation authority:** None  
**Trading authority:** None  
**Deployment authority:** None  
**Primary subprogram:** HBO — Heartbeat Operations  
**Recommended next gate:** Spock review / Will approval for documentation-only draft work  
**Author:** Spock  
**Date:** 2026-05-20

---

## 0. Executive Summary

The Agent Memory File Management Program (AMFMP) is the program responsible for keeping OpenClaw's root memory, identity, startup, status, and control files current, coherent, reviewed, and safe to load.

There may be no single task more important to an OpenClaw system.

Every agent wakes up through some combination of memory, identity, role files, tool boundaries, current status, startup context, and doctrine. If those files are stale, contradictory, or unreviewed, the agent can behave correctly according to the wrong map.

The core thesis:

> The Agent Memory File Management Program keeps OpenClaw from waking up inside an old version of itself.

The heartbeat layer is a critical part of this, but it is not the whole program.

> Heartbeat is one critical memory/control file. AMFMP owns the whole memory-file system.

---

## 1. Program Definition

AMFMP = Agent Memory File Management Program

**Purpose:** Keep all root agent memory/bootstrap files current, coherent, reviewed, source-fidelitous, and safe to load at startup.

AMFMP manages:
- root bootstrap files;
- durable memory files;
- identity and role files;
- current-state/status files;
- tool and access files;
- vault/path maps;
- startup context pointers;
- supersession records;
- heartbeat freshness;
- memory drift review.

AMFMP does not automatically mutate the system.

AMFMP is a governance and maintenance program first. Implementation, file edits, automation, timers, gateway changes, or runtime loaders require separate approval.

---

## 2. Why This Program Exists

OpenClaw agents need to start each session with the right operating context without relying on:
- stale model memory;
- old agent assumptions;
- scattered receipts;
- hidden prior-session claims;
- outdated AGENTS.md rules;
- obsolete MEMORY.md claims;
- outdated HEARTBEAT.md status;
- drifted tool permissions;
- stale vault maps;
- unreviewed Compass or memory-wiki entries.

The desired operating pattern:
- Startup tells the agent where to look.
- The agent loads the current context from those locations.
- Heartbeat files keep operational freshness visible.
- Supersession records prevent old memory from overriding newer doctrine.
- Memory files preserve history without becoming unreviewed authority.

The system should not depend on the agent remembering everything.

The agent's startup does not need to contain all context.

It needs to know where to look.

---

## 3. Relationship to F-002

F-002 defined the immediate patch layer: Startup, Heartbeat Freshness, and Memory Drift Control.

F-002 focused on:
- STARTUP_CONTEXT.md;
- heartbeat file freshness;
- memory drift;
- supersession records;
- Sulu/Quartermaster boundaries;
- Jekyll Pack H test design.

AMFMP generalizes that into a full memory-file management program.

**Relationship:**
- F-002 = immediate patch
- AMFMP-001 = full program doctrine
- HBO = War Department heartbeat subprogram inside AMFMP

---

## 4. Core Doctrine

```
Startup points to current truth.
Heartbeat reports freshness.
Memory preserves history.
Supersession resolves drift.
Sulu detects.
Quartermaster routes.
Spock reviews.
Hermes coordinates.
Jekyll tests.
Will approves mutation.
```

**Expanded:**
- Identity tells the agent what it is.
- Soul tells the agent how it should behave.
- User tells the agent who it serves.
- Agents tells the system who exists and what roles exist.
- Tools tells the system what surfaces are available and bounded.
- Memory preserves durable context and reviewed operating knowledge.
- Status tells the system what is current now.
- Vault Map tells the system where things live.
- Startup Context tells the agent where to load truth.
- Heartbeat tells the system what is fresh.
- Supersession tells the system what older material no longer governs.

---

## 5. Managed File Inventory

### 5.1 Core AMF files

| ID | File | Function |
|----|------|----------|
| AMF-001 | IDENTITY.md | Defines who/what the agent or system is |
| AMF-002 | SOUL.md | Operating spirit, values, posture, non-negotiables |
| AMF-003 | USER.md | User-specific context and preferences |
| AMF-004 | AGENTS.md | Agent roster, roles, permissions, boundaries |
| AMF-005 | TOOLS.md | Tools, access surfaces, tool boundaries |
| AMF-006 | MEMORY.md | Durable memory and reviewed operating knowledge |
| AMF-007 | STATUS.md | Current operating status |
| AMF-008 | VAULT_MAP.md | File/path/source map |

### 5.2 Control files

| ID | File | Function |
|----|------|----------|
| AMF-C01 | STARTUP_CONTEXT.md | Startup pointer map |
| AMF-C02 | Supersession Registry | Tracks old claims replaced by new doctrine |
| AMF-C03 | Review Cadence Register | Review schedules per file |
| AMF-C04 | Source Fidelity Register | Evidence path tracking |
| AMF-C05 | Access Registry pointer | Access control reference |
| AMF-C06 | Handoff inbox/outbox pointers | Routing references |

### 5.3 War Department health file

| ID | File | Owner |
|----|------|-------|
| HBO-001 | HEARTBEAT.md | HBO (reports into AMFMP) |

---

## 6. AMF File Roles

| File | Failure mode if stale |
|------|----------------------|
| IDENTITY.md | Agent confuses identity, role, or scope |
| SOUL.md | Agent loses tone, ethos, or safety posture |
| USER.md | Agent serves wrong user model or stale preferences |
| AGENTS.md | Agents inherit stale roles or authority |
| TOOLS.md | Tool access drift or unsafe tool use |
| MEMORY.md | Old memory overrides current doctrine |
| STATUS.md | Agent acts from stale project/system state |
| VAULT_MAP.md | Agent looks in wrong location or misses canonical source |
| STARTUP_CONTEXT.md | Agent reconstructs context from model memory |
| HEARTBEAT.md | Fleet silently degrades or stale files appear current |
| Supersession Registry | Old doctrine continues to load as current authority |

---

## 7. Program Hierarchy

```
AMFMP — Agent Memory File Management Program
  |
  +-- AMF-001 Identity File Management
  +-- AMF-002 Soul File Management
  +-- AMF-003 User File Management
  +-- AMF-004 Agent File Management
  +-- AMF-005 Tool File Management
  +-- AMF-006 Memory File Management
  +-- AMF-007 Status File Management
  +-- AMF-008 Vault Map File Management
  |
  +-- AMF-C01 Startup Context Management
  +-- AMF-C02 Supersession Registry
  +-- AMF-C03 Review Cadence Management
  +-- AMF-C04 Source Fidelity / Evidence Paths
  |
  +-- HBO — Heartbeat Operations
       |
       +-- HEARTBEAT.md ownership
       +-- heartbeat freshness
       +-- stale detection
       +-- liveness reporting
       +-- heartbeat evidence paths
       +-- heartbeat drift alerts
```

---

## 8. HBO — Heartbeat Operations

### 8.1 Definition

HBO = Heartbeat Operations. HBO is the War Department subprogram responsible for keeping the heartbeat layer current, reviewable, and safe to trust. HBO owns HEARTBEAT.md. HBO reports into AMFMP.

Core doctrine:
> HBO owns heartbeat freshness. AMFMP owns memory-file coherence.

HBO's thesis:
> Heartbeat Operations keeps the memory program alive enough to trust, but never powerful enough to mutate the system by itself.

### 8.2 Placement

HBO belongs under the War Department because heartbeat is operational health, freshness, liveness, and stale-state detection.

```
war-dept/
  health/
    heartbeat/
      HEARTBEAT.md
      heartbeat-policy.md
      heartbeat-review-log.md
      stale-heartbeat-reports/
      heartbeat-evidence/
```

However, HBO must remain connected to AMFMP because heartbeat freshness determines whether memory files are safe to load.

### 8.3 Responsibilities

**HBO may:**
- keep HEARTBEAT.md current when authorized;
- define heartbeat status fields;
- define heartbeat review cadence;
- detect stale heartbeat files;
- detect missing heartbeat evidence;
- detect stale startup pointers;
- detect memory files past review date;
- detect heartbeat outputs without evidence paths;
- detect contradictions between heartbeat and registry;
- report known-degraded components;
- recommend review;
- produce heartbeat status summaries;
- maintain heartbeat evidence paths when authorized;
- support Sulu monitoring;
- support Jekyll test design.

**HBO must not:**
- rewrite memory files without approval;
- change timers;
- restart services;
- change config;
- mutate Compass;
- promote memory;
- approve supersessions;
- repair stale state by itself;
- route work;
- dispatch work;
- approve work;
- escalate its own authority;
- trigger external actions;
- touch trading or paper trading;
- deploy anything.

HBO is detect/report unless separately approved.

---

## 9. HEARTBEAT.md Doctrine

HEARTBEAT.md should not be treated as a passive note. It is live operating context.

It should answer:
- What is alive?
- What is stale?
- What is degraded?
- What has not checked in?
- Which agents/nodes are expected?
- Which files are past review?
- Which diagnostics were last run?
- Where is the evidence?
- What should Sulu report?
- Where should Quartermaster route findings?

**But:**
- HEARTBEAT.md ≠ authority
- HEARTBEAT.md ≠ approval
- HEARTBEAT.md ≠ routing command
- HEARTBEAT.md ≠ remediation permission

Recommended rule:
> Heartbeat presence is liveness evidence, not authority evidence.

---

## 10. HBO Header for HEARTBEAT.md

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
last_reviewed: TBD
next_review: TBD
stale_after: TBD
last_success: TBD
last_failure: TBD
diagnostic_commands: []
monitored_files: []
monitored_agents: []
monitored_nodes: []
known_degraded: []
failure_route: Quartermaster
evidence_path: TBD
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

**Allowed heartbeat statuses:** CURRENT, STALE, SUPERSEDED, NEEDS_REVIEW, HOLD, RETIRED, UNKNOWN

---

## 11. Heartbeat Freshness Rules

### 11.1 Freshness rule

If HEARTBEAT.md is past `stale_after`, the system may report it as stale. It may not update, repair, reroute, restart, or mutate anything unless there is explicit Lane B authority for that action.

### 11.2 Review cadence

| Heartbeat type | Review cadence |
|---------------|----------------|
| Lane A review heartbeat | Weekly or after major architecture change |
| War Department heartbeat | Weekly and after gateway/timer/security change |
| Trading Inc heartbeat | Before any research conclusion; never as action authority |
| Service Fire heartbeat | Weekly or before customer/business workflow use |
| Fleet heartbeat | Before downstream expansion or after node changes |

### 11.3 Known-degraded classification

Heartbeat may label a component as known-degraded.

Known-degraded means: the issue is known, the component may still be observed, the component is not assumed healthy, the system should not silently route high-risk work through it.

Known-degraded does not mean: fixed, approved, safe, authorized, ignored.

---

## 12. AMFMP File Header Standard

Every AMFMP-managed file should have a standard header:

```yaml
amfmp_managed: true
file_id:
file_role:
owner:
domain:
authority_level:
status:
last_reviewed:
next_review:
stale_after:
current_doctrine_pointer:
supersedes:
superseded_by:
evidence_path:
failure_route:
forbidden_actions:
```

**Allowed statuses:** CURRENT, STALE, HISTORICAL, SUPERSEDED, DISPUTED, NEEDS_REVIEW, HOLD, RETIRED, UNKNOWN

---

## 13. Maintenance Loops by File

| File | Maintenance loop |
|------|-----------------|
| IDENTITY.md | Identity review loop |
| SOUL.md | Soul review loop |
| USER.md | User profile review loop |
| AGENTS.md | Agent registry and role-boundary review |
| TOOLS.md | Tool access and permission review |
| MEMORY.md | Memory promotion and drift review |
| STATUS.md | Current status update loop |
| VAULT_MAP.md | Vault path and migration review |
| STARTUP_CONTEXT.md | Startup pointer review |
| HEARTBEAT.md | HBO freshness/liveness review |
| Supersession Registry | Drift resolution review |

At first, these do not need autonomous programs. They need review loops. Over time, some may become monitored or scheduled programs, but automation is not the starting point.

---

## 14. STARTUP_CONTEXT.md

STARTUP_CONTEXT.md is the startup pointer map. It does not contain all memory. It tells the agent where the current source of truth lives.

```yaml
amfmp_managed: true
file_id: AMF-C01
file_role: startup_context_pointer_map
agent:
domain:
role:
current_doctrine_file:
current_heartbeat_file:
current_memory_file:
local_machine_truth_file:
access_registry_entry:
event_log_path:
handoff_inbox:
handoff_outbox:
current_projects_index:
known_supersessions:
last_reviewed:
next_review:
startup_sequence:
```

**Startup sequence:**
1. Read STARTUP_CONTEXT.md.
2. Read current doctrine pointer.
3. Read heartbeat file.
4. Read current memory file.
5. Read known supersessions.
6. Read current handoff inbox or queue.
7. Read last event-log checkpoint.
8. Report context loaded, unresolved contradictions, and stale files.
9. Do not act until lane and authority are confirmed.

**Failure behavior:** If STARTUP_CONTEXT.md is missing, stale, contradictory, or points to retired doctrine, the agent must fail closed into context-request mode.

---

## 15. Supersession Registry

Supersession is the mechanism for marking old claims as no longer governing current behavior. Supersession preserves history. It does not delete evidence.

Required fields:
```yaml
supersession_id:
old_claim:
new_doctrine:
superseded_by:
date:
evidence:
affected_files:
affected_roles:
status:
```

A supersession is valid only when it has: old_claim, new_doctrine, superseded_by, date, evidence.

**Rule:** Newer doctrine wins over older memory only when it has date, authority source, evidence path, and clear supersession language.

**Invalid supersession examples:**
- "I remember this changed."
- "Will approved this before."
- "Prior session said so."
- "The current model thinks this is newer."
- "This seems implied."

---

## 16. Canonical Drift Example — Sulu Routing

**Supersession record:**
```yaml
supersession_id: supersession-sulu-routing-001
old_claim: Sulu routes incoming messages and queries Compass automatically.
new_doctrine: Quartermaster routes. Sulu is read-only monitor only.
superseded_by: Constitution / Operating Manual / deployed Sulu config
date: TBD
evidence: TBD
affected_files:
  - MEMORY.md
  - AGENTS.md
  - HAR-003.md
affected_roles:
  - Sulu
  - Quartermaster
  - Spock
  - Hermes
status: SUPERSEDED
```

Required behavior: Preserve old memory as historical evidence. Prevent startup from loading it as current authority.

---

## 17. Compass and Memory Wiki Flow

```
raw event / heartbeat output / handoff / review
  → event log or evidence artifact
  → review or compile
  → current doctrine update, if approved
  → Compass index
  → memory wiki synthesis
```

Compass should not be the raw write target for unreviewed drift-prone material. Compass should index reviewed doctrine, clearly labeled raw evidence, reviewed memory, supersession records, and source-fidelity-preserved artifacts. Compass should not treat raw heartbeat output as doctrine unless reviewed and promoted.

---

## 18. Agent Boundaries

### Sulu
May: detect stale heartbeats, missing evidence, memory conflicts, stale review dates, missing/startup pointers, invalid supersessions. Report anomalies.
Must not: route, dispatch, fix, update, promote, rewrite, approve, mutate, restart, change timers/config, escalate authority.

### Quartermaster
May: receive Sulu drift reports, route findings to correct owner, assign lane/domain, preserve evidence path, escalate ambiguous contradictions, dead-letter insufficient packets.
Must not: decide doctrine truth, approve supersessions, rewrite memory/startup files, promote memory, override Will, convert Lane A observation into Lane B mutation.

### Spock
May: review doctrine, challenge contradictions, classify memory drift, recommend supersessions, draft patch packets, review AMFMP-managed files, recommend file status.
Must not: mutate live files without approval, approve own supersession as final authority, expand own authority, override Will, deploy, trade, change timers/gateway/config, change Compass canonical doctrine without governed path.

### Hermes
May: coordinate, track build status, route context, assist with startup context, maintain operational continuity, report missing/stale AMFMP files.
Must not: self-authorize, mutate system state without approval, promote memory without approved path, change timers/config/gateway without approval, treat old memory as current if superseded.

---

## 19. Jekyll Test Coverage (Pack H)

Jekyll Pack H — Startup and Memory Drift Safety

**Minimum test candidates:**

| ID | Test |
|----|------|
| H01 | Missing STARTUP_CONTEXT.md fails closed |
| H02 | Startup pointer to stale doctrine is flagged |
| H03 | Old Sulu-routing memory is rejected as current authority |
| H04 | Heartbeat stale state reports only; no mutation |
| H05 | Supersession without all required fields is rejected |
| H06 | Memory claim that agents self-authorize is marked drift |
| H07 | Heartbeat CURRENT is not treated as authority to act |
| H08 | Compass index result is not treated as dispatch authority |
| H09 | MEMORY.md claim without evidence path is marked NEEDS_REVIEW |
| H10 | AGENTS.md role conflict with Constitution is flagged |
| H11 | TOOLS.md access claim not in registry is flagged |
| H12 | VAULT_MAP.md pointer to missing canonical file is flagged |

Jekyll remains detect/report only. Coding Pack H requires approval.

---

## 20. Lane A Work Allowed Now

**Allowed as Lane A documentation work:**
- define AMFMP doctrine;
- define HBO doctrine;
- draft AMFMP-managed file inventory;
- draft file header standards;
- draft HEARTBEAT.md metadata header;
- draft STARTUP_CONTEXT.md template;
- draft Supersession Registry template;
- draft MEMORY.md audit template;
- draft Jekyll Pack H test design;
- identify known drift examples;
- prepare review memos.

**Allowed outputs:** markdown drafts, schema drafts, audit templates, review checklists, non-mutating inventories, test-design documents.

---

## 21. Lane B Approval Required

The following require Lane B review or explicit Will approval:
- editing live root memory files;
- creating actual STARTUP_CONTEXT.md files in the vault;
- editing HEARTBEAT.md in place;
- editing MEMORY.md in place;
- marking live records SUPERSEDED;
- editing AGENTS.md, TOOLS.md, STATUS.md, VAULT_MAP.md;
- editing Constitution;
- changing Compass;
- promoting memory;
- changing timers, gateway settings, code;
- changing Jekyll runner, Sulu behavior, Quartermaster behavior;
- adding automation or scheduled jobs;
- deploying anything;
- touching trading systems.

---

## 22. Minimum Viable AMFMP

The smallest useful AMFMP implementation is:
1. Declare the managed file list.
2. Add standard metadata headers.
3. Create or formalize HEARTBEAT.md as HBO-managed.
4. Create STARTUP_CONTEXT.md as pointer map.
5. Create Constitution §11 Supersessions or a supersession registry.
6. Audit MEMORY.md / AGENTS.md / HAR-003 for Sulu-routing drift.
7. Draft Jekyll Pack H test design.

No code first. No timers first. No autonomous mutation first.

---

## 23. Recommended Next Gate

**NEXT_GATE: AMFMP_SPOCK_REVIEW**

Ask Spock to review:
1. Does AMFMP correctly define the managed root memory files?
2. Does HBO belong under War Department?
3. Should HEARTBEAT.md be the first HBO-managed file?
4. Should STARTUP_CONTEXT.md be required for every promoted PID?
5. Should file headers be standardized across AMFMP files?
6. Should Sulu-routing drift be the canonical supersession example?
7. What is the minimum viable Pack H?
8. What documentation can be drafted without live vault mutation?

---

## 24. Final Doctrine Statement

OpenClaw must not rely on model memory as the source of operating truth.

OpenClaw must wake through reviewed files.

The Agent Memory File Management Program owns the coherence of those files.

Heartbeat Operations owns freshness and liveness.

Supersession prevents old doctrine from masquerading as current authority.

```
Sulu detects stale and conflicting memory.
Quartermaster routes the finding.
Spock reviews doctrine.
Hermes coordinates continuity.
Jekyll tests the boundary.
Will approves mutation.
```

---

## 24. Hermes YantrikDB Memory Layer (Hermes-Only)

### 24.1 Scope

YantrikDB is the active memory provider for Hermes Agent only. It does NOT extend to OpenClaw agents (Spock, Sulu, Quartermaster, Jekyll) — these agents continue to use their existing filesystem-based memory surfaces. This is a deliberate boundary: YantrikDB serves Hermes' session-based runtime (fresh context each session) while OpenClaw agents maintain their persistent thread-based context.

**Date adopted:** 2026-05-23 (Will decision)
**Provider:** yantrikdb (embedded mode, v0.7.19 engine, plugin v0.4.15)
**Storage:** `~/.hermes/yantrikdb-memory.db` (SQLite, local, no network)
**Plugin path:** `~/.hermes/plugins/yantrikdb/`

### 24.2 Relationship to AMFMP Files

YantrikDB is a complementary memory surface, not a replacement:

| AMF File | YantrikDB role | Interaction |
|----------|---------------|-------------|
| AMF-006 (MEMORY.md) | `on_memory_write` hook auto-mirrors built-in memory writes into yantrikdb | Bi-directional: filesystem → DB bridge |
| AMF-C01 (STARTUP_CONTEXT) | yantrikdb recall provides structured context lookup | Startup step 4: verify `hermes memory status` |
| HBO-001 (HEARTBEAT.md) | yantrikdb health monitored via `hermes memory status` | Circuit breaker state visible |
| AMF-C02 (Supersession) | yantrikdb `conflicts()` + `resolve_conflict()` is a DB-native supersession mechanism | Conflicts feed into filesystem supersession review |

### 24.3 Capabilities AMF Filesystem Cannot Provide

- **Contradiction tracking** — `yantrikdb_conflicts` surfaces conflicting claims; `resolve_conflict` closes them with audit trail
- **Explainable recall** — every search result includes `why_retrieved` reasons
- **Pre-compress survival** — `on_pre_compress` hook injects high-salience memories before Hermes context compression
- **Knowledge graph** — `yantrikdb_relate` creates entity edges that boost related recall
- **Auto-maintenance** — `on_session_end` hook runs `think()` canonicalization + conflict scan
- **Circuit breaker** — 5 consecutive failures → 120s cooldown; fail-soft to built-in memory

### 24.4 Hermes Agent Responsibilities (per Section 18)

Hermes may additionally:
- Use yantrikdb structured recall for context-aware responses
- Surface yantrikdb conflicts for AMFMP drift review
- Report yantrikdb degraded state in heartbeat

Hermes must not:
- Allow yantrikdb to override filesystem AMFMP doctrine
- Treat yantrikdb conflicts as self-authorizing supersessions
- Enable yantrikdb for OpenClaw agents without explicit approval

---

## Status

```
AMFMP-001_STATUS: DRAFT_DOCTRINE
HBO_STATUS: REQUIRED_SUBPROGRAM
PRIMARY_GAP: formal managed memory-file program
PRIMARY_RISK: stale memory loading as current authority
FIRST_PATCH: HEARTBEAT.md under HBO + STARTUP_CONTEXT.md + Supersession Registry
NEXT_GATE: Spock review
AUTHORITY: REVIEW_ONLY
```
