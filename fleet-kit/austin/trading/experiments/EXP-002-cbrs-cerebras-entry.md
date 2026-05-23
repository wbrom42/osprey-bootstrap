# EXP-002 — CBRS Cerebras Systems Entry

**Experiment ID:** EXP-002
**Date Proposed:** 2026-05-21
**Proposed By:** Spock (S-2)
**Tier:** Micro (<$5K) — auto_close_72h
**Sleeve:** Active Experiments

---

## Thesis

Cerebras Systems is the nearest pure-play competitor to Nvidia in AI training silicon. Pre-IPO valuation ~$4B. Public debut creates a price discovery event where institutional positioning and retail sentiment diverge — creating entry windows. The CBRS wafer-scale architecture is a differentiated moat in a market paying 10-15× revenue for anything AI silicon. The market will find equilibrium price; we enter below it.

## Strategy Rules

**Entry Zones:**
- Starter: $260-280 (25% allocation) — current price $280.50, 1.8% above zone
- Scale-In: $220-245 (25% allocation)
- Deep Value: $170-200 (25% allocation)
- Final 25% reserved for re-entry signal

**Exit:**
- Take profit: +30%, +50%, +100% scale-out (1/3 each at each level)
- Stop loss: -20% hard stop at position level
- Time stop: 90 days without positive P&L → close

**Position Sizing:**
- Allocation: $5,000 (5.2% of active sleeve, 5.2% of long-term sleeve capacity)
- Max position: $5,000
- Single tranche max: $1,250 (25% of position)

**Instrument:** CBRS common stock

## Risk Parameters

| Parameter | Value |
|-----------|-------|
| Requested Allocation | $5,000 |
| Max Drawdown (hard stop) | -20% ($1,000 loss) |
| Time Limit | 90 days |
| Max Positions | 1 position, 4 tranches |
| Max Position Size | $5,000 |

## Success Metric

Position exits at +30% or higher on full allocation. Compound return >15% annualized if held to scale-out.

## Kill Conditions

- [x] -20% drawdown from peak → PAUSE, review
- [x] Thesis invalidated: CBRS loses >50% of AI training market narrative (competitor leapfrog, architecture obsolescence)
- [x] Time limit expired without positive edge (90 days)
- [ ] Correlated failure with another active experiment (N/A — first IPO position)

## Dependencies

- cbrs-position-monitor.py (already running, 30-min cadence)
- Alpaca Paper Account3
- yfinance data feed

---

## EC Protocol

| Step | Status |
|------|:------:|
| Classify | ✅ Micro tier — single-stock entry, defined zones, mechanical exit |
| Scope | ✅ EXP-002 proposal filed |
| Pre-mortem | ✅ IPO volatility risk — gap-down risk on negative news. Mitigation: 4-tranche entry, no single entry point. Position sizing limits loss to $1,000. |
| Readiness | ✅ Monitor running. Entry zone defined. Paper account funded. |
| Gate | APPROVE — Hermes auto_close_72h (Micro tier) |

**Deploy immediately on dip into $260-280 zone. No Will approval needed per desk gate structure.**
