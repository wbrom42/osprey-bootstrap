# Fleet Update — Service Manager Node v1.1
# Shipped: 2026-05-23
# Update type: CORE + JEKYLL + GOVERNANCE

## What Changed

### Core DNA (7 files)
| File | Change |
|------|--------|
| AGENTS.md | Updated with current doctrine: AMFMP/HBO, inbox sweep, Pack H, startup protocol |
| SOUL.md | Current Service Manager persona |
| HEARTBEAT.md | **NEW** — 24-field HBO master schema, stale detection, known_degraded tracking |
| STARTUP_CONTEXT.md | **NEW** — Standardized startup pointer map, failure behavior, supersession registry |
| OSPREY_CONSTITUTION.md | Updated with Two-Lane Architecture, execution posture |
| OSPREY_OPERATING_MANUAL.md | Updated with Protocol Layer Doctrine, project initiation |
| MEMORY.md | **NEW** — Service Manager node memory, fleet boundaries, red lines |

### Governance (2 files)
| File | Change |
|------|--------|
| AMFMP-001 | **NEW** — Agent Memory File Management Program (parent doctrine) |
| HBO | **NEW** — Heartbeat Operations Bureau (HEARTBEAT.md schema + stale detection) |

### Jekyll (17 files — was 11)
| File | Change |
|------|--------|
| pack_isolation.py | Unchanged |
| pack_b_lane_classification.py | Unchanged |
| pack_c_domain_isolation.py | Unchanged |
| pack_d_authority_laundering.py | Unchanged |
| pack_e_acceptance_rate.py | Unchanged |
| pack_f_shadow_swarm.py | Unchanged |
| pack_g_control_surface.py | **RENAMED** from pack_g_cron_safety.py — expanded with access registry + truth folder tests |
| sulu_assertion_test.py | Unchanged |
| jh001_handoff_format.py | **NEW** — JSON handoff format compliance |
| jh002_har003_staleness.py | **NEW** — HAR-003 staleness check (48h) |
| jh003_cron_health.py | **NEW** — Cron fleet disabled >24h detection |
| jh004_supply_chain_integrity.py | **NEW** — Supply chain integrity (GitHub breach response) |
| jh005_startup_context_integrity.py | **NEW** — STARTUP_CONTEXT.md existence + pointer resolution |
| jh006_doctrine_staleness.py | **NEW** — All doctrine file staleness check |
| jh007_heartbeat_staleness.py | **NEW** — HEARTBEAT.md freshness verification |
| run-jekyll.sh | Updated with all JH assertions + Pack H |
| JEKYLL_DOCTRINE.md | Unchanged |

### Removed
| File | Reason |
|------|--------|
| pack_g_cron_safety.py | Superseded by pack_g_control_surface.py |

## Test Results (Father Node)
All 7 JH assertions + 8 Pack assertions = 15 total.
Current: 13/15 PASS (2 pre-existing: JH-001 legacy handoffs, JH-003 disabled crons).
Pack G: 9/9 PASS. Pack H: 3/3 PASS.

## Deployment Notes
- Fleet kit is file-based — no installation step needed
- Service Manager reads from fleet wiki (wiki/fleet/) for father updates
- Jekyll suite runs daily at 6am local
- HEARTBEAT.md staleness enforced by JH-007 at 7d

## Next Fleet Update Expected
When D-015 Beever Atlas Phase 1 deploys (Neo4j + Qdrant + ingest pipeline).
Or when first Service Manager domain data integration is ready.
