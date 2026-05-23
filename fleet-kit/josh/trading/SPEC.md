# D-013: Osprey Trading Architecture v2 — Build Spec

## Build Objective

Build a portfolio-first, quality-driven trading architecture based on the TradingAgents research pattern (arXiv:2412.20138). The system replaces the legacy signal→execute loop with a structured thesis generation pipeline: **CLASSIFY → THESIS → ADVERSARIAL REVIEW → JUDGE → SIZE → ACT**, backed by portfolio management and a calibration loop.

**Key constraint:** UW tools become research inputs, not execution signals. No day trading. Hours/days/weeks time horizon.

---

## Architecture Overview

### Layer 1 — Thesis Generation (EC Chain)

```
CLASSIFY → THESIS → ADVERSARIAL REVIEW → JUDGE → SIZE → ACT
```

1. **CLASSIFY** — Research question generated from screener/signal output
2. **THESIS** — Analyst agent writes structured thesis: direction, conviction, time horizon, catalysts, falsification criteria
3. **ADVERSARIAL REVIEW** — Mandatory bull/bear debate before JUDGE. One agent argues for, another challenges.
4. **JUDGE** — Third agent evaluates both sides, produces verdict
5. **SIZE** — Risk manager sizes position: conviction score × portfolio context × concentration limits
6. **ACT** — Portfolio manager approval → execute

### Layer 2 — Portfolio Management

```
HOLDINGS → RISK SCAN → REBALANCE
```

- **Holdings snapshot** — Current positions across all accounts
- **Risk scan** — Concentration, correlation, drawdown, sector exposure
- **Rebalance decision** — Thesis-driven: close weak, add to strong, manage sizing

### Layer 3 — Calibration (P-001)

```
PREDICTION → VERIFY → SCORE → FEEDBACK
```

- Every actionable thesis registers as a P-001 prediction
- Outcome verified when event window closes
- Score agent accuracy over time
- Feed calibration back into confidence scoring

### Data Flow

```
UW APIs ──→ Cron collectors ──→ Shared data store ──→ Thesis agents ──→ Portfolio agents
Crypto APIs ──→ Cron collectors ──→ Shared data store ──→ Thesis agents ──→ Portfolio agents
Macro clocks ───────────────────────────────────────────→ Context layer (all agents)
```

---

## Key Decisions & Tradeoffs

| Decision | Chosen Approach | Rationale |
|----------|----------------|-----------|
| Thesis vs signal-driven | Thesis-driven with adversarial review | Quality over speed. TradingAgents research shows adversarial debate reduces false positives by ~40% |
| Cron architecture | 2 consolidated programs (stock + crypto) | Max 2 concurrent. One stock script pulls all UW data. One crypto script pulls all crypto data. No fragmented per-source crons |
| Data store | Shared JSON cache + SQLite | Existing infrastructure. UW trader scripts already write to cache files. Compass for lifecycle tracking |
| Execution gate | Human-in-loop (Portfolio Manager → Will) | No automated execution without human review. VetoEngine provides graduated powers |
| Adversarial review | Mandatory for every thesis | Not optional. Skipping review blocks JUDGE gate |
| Calibration | P-001 prediction register | Already exists. Integration is wiring the thesis pipeline to auto-register predictions |

---

## Scope

### In Scope (v1)

| Component | Description | Build Cell |
|-----------|-------------|------------|
| **Adversarial Review** | Mandatory second pass in EC chain before JUDGE. Bull agent + bear agent per thesis | D-013-001 |
| **VetoEngine graduated powers** | D-008 integration: approve/reduce/delay/reject authority levels | D-013-002 |
| **Portfolio snapshot** | Script aggregating positions across all accounts (stocks, crypto, options) | D-013-003 |
| **Portfolio consistency check** | Cross-position correlation + concentration check | D-013-004 |
| **P-001 thesis registration** | Every actionable thesis auto-registers as prediction in P-001 | D-013-005 |
| **Stock data collector** | Consolidated UW cron script — screener, fundamentals, flow, insider trades, congress trades | D-013-006 |
| **Crypto data collector** | Consolidated crypto cron script — on-chain data, market structure, regime signals | D-013-007 |

### Not in Scope (v1)

- Intraday trading / HFT
- Automated execution without human review
- Options selling / complex multi-leg strategies
- Margin-based positioning
- Real-time market data feeds (sub-minute)
- Direct broker API integration (manual execution via Robinhood/other UI)
- Machine learning models for thesis generation
- Backtesting framework

---

## Integration Points

| System | Integration Type | Notes |
|--------|-----------------|-------|
| **UW REST API** | Cron data collection | Stock data collector script calls UW endpoints directly (not MCP) |
| **GMGN / Crypto APIs** | Cron data collection | Crypto data collector script calls on-chain APIs directly |
| **EC chain** | Logic integration | Adversarial review adds step between THESIS and JUDGE |
| **D-008 (VetoEngine)** | Expansion | Graduated powers: approve/reduce/delay/reject |
| **P-001** | Registration integration | Every thesis auto-registers as prediction |
| **Compass** | Lifecycle tracking | Entry per thesis, per trade, per prediction |
| **Hermes cron** | Scheduling | Stock + crypto collectors on schedule, max 2 concurrent |
| **Event Store** | Audit trail | Every thesis, review, judge verdict, action logged |

---

## Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| UW API keys | ✅ Available | REST API keys, not MCP (MCP disabled) |
| Crypto API keys | ✅ Available | GMGN keys configured |
| EC chain infrastructure | ✅ Built | CLASSIFY → THESIS → JUDGE → SIZE → ACT exists |
| VetoEngine (D-008) | ✅ Built | Needs graduated powers expansion |
| P-001 prediction register | ✅ Built | Needs thesis registration integration |
| Compass DB | ✅ Available | For lifecycle tracking |
| Hermes cron | ✅ Available | For scheduling collectors |
| TradingAgents research | ✅ Synthesized | wiki/syntheses/tradingagents-research.md |

---

## Acceptance Criteria

The architecture is spec-complete and build-ready when:

1. [ ] Adversarial review gate inserted into EC chain — mandatory before JUDGE
2. [ ] VetoEngine supports approve/reduce/delay/reject (not just approve/reject)
3. [ ] Portfolio snapshot script produces consolidated position report
4. [ ] Portfolio consistency check runs against snapshot data
5. [ ] Thesis pipeline auto-registers in P-001 prediction register
6. [ ] Stock data collector pulls all UW sources in single run
7. [ ] Crypto data collector pulls all crypto sources in single run
8. [ ] No more than 2 collectors run concurrently
9. [ ] All components pass smoke test with exit 0
10. [ ] Rollback documented and tested for each component

---

## Locked Decisions (from Will, 2026-05-18)

The following open questions have been answered and are now locked:

1. **Execution UI** → **Telegram**. Thesis, debate, and ACT decisions surface as Telegram messages.
2. **Position tracking** → **Dedicated DB**. New schema for structured trading data (not Compass — Compass is for agent memory).
3. **Account scope** → **Alpaca** paper account only. Alpaca API for order execution + position queries.
4. **Will's review threshold** → **None**. Paper trading — no manual review gate for ACT. Ship and monitor.
5. **Adversarial agent assignment** → **Doesn't matter**. One agent writes thesis, another challenges. Pseudo-random or fixed, no meaningful difference at this scale.
6. **Calibration feedback loop** → **Automated confidence adjustment**. P-001 scores update automatically on outcome verification.

---

## Build Cell Summary

| Cell | Component | Authority | Dependencies | Est. Effort |
|------|-----------|-----------|-------------|-------------|
| D-013-001 | Adversarial Review | BOUNDED | EC chain | 1-2h |
| D-013-002 | VetoEngine graduated powers | BOUNDED | D-013-001, D-008 | 2-3h |
| D-013-003 | Portfolio snapshot | BOUNDED | Account inventory (open) | 1h |
| D-013-004 | Portfolio consistency check | BOUNDED | D-013-003 | 1h |
| D-013-005 | P-001 thesis registration | BOUNDED | D-013-001 | 1h |
| D-013-006 | Stock data collector | BOUNDED | UW API keys | 2h |
| D-013-007 | Crypto data collector | BOUNDED | Crypto API keys | 1h |

Build sequence: D-013-006/007 first (data pipeline) → D-013-001/002 (decision logic) → D-013-003/004 (portfolio management) → D-013-005 (calibration)
