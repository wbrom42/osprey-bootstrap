# EXP-004 — Hawkes Regime Momentum (Stocks)

**Experiment ID:** EXP-004
**Date Proposed:** 2026-05-21
**Proposed By:** Spock (S-2)
**Tier:** Standard ($5-20K) — EC Protocol + Will approval required
**Sleeve:** Active Experiments

---

## Thesis

The Hawkes process state machine (HAWK_0 → HAWK_1 → Active) captures momentum regime changes on daily timeframe with a mechanical, non-discretionary signal. Validated on crypto in the league (closed May 18) — the framework correctly identified regime transitions. Applying it to S&P 500 liquid equities tests whether the state machine generalizes across asset classes. If it does, it's a reusable signal engine for paper and eventually live.

## Strategy Rules

**Entry:**
- HAWK_0: Never triggered. Monitor only.
- HAWK_1: First spike done, exited to flat. WATCH — second spike is entry signal.
- Active: Second spike confirmed. Enter long. 2% allocation per signal.
- Max 5 concurrent positions.

**Exit:**
- Take profit: Trailing stop at 2× ATR (14-day)
- Stop loss: -15% from entry
- Time stop: 60 days without new HAWK_1 signal — close position

**Position Sizing:**
- Allocation: $7,500 (7.9% of active sleeve)
- Per position: $1,500 (2% of $75K notional, scaled to $7.5K allocation)
- Max positions: 5 concurrent

**Instrument:** S&P 500 liquid equities (top 500 by market cap)
**Data:** yfinance daily OHLCV — no API cost

## Risk Parameters

| Parameter | Value |
|-----------|-------|
| Requested Allocation | $7,500 |
| Max Drawdown (hard stop) | -20% at experiment level ($1,500 loss) |
| Time Limit | 180 days (evaluation period) |
| Max Positions | 5 concurrent |
| Max Position Size | $2,250 (30% of allocation concentration limit) |

## Success Metric

Sharpe ratio >1.0 over 180-day evaluation. Win rate >50%. Positive alpha vs SPY buy-and-hold over same period.

## Kill Conditions

- [x] -20% drawdown from peak → PAUSE, review
- [x] Thesis invalidated: Sharpe <0.5 after 90 days, or win rate <35%
- [x] Time limit expired without positive edge (180 days)
- [x] Correlated failure with another active experiment (D-001 NeuroTrader)

## Dependencies

- yfinance daily data (free, no API key)
- Hawkes process library (existing from crypto league)
- Alpaca Paper Account3 for execution
- D-012 forecasting ledger for grading

---

## EC Protocol

| Step | Status |
|------|:------:|
| Classify | ✅ Standard tier — momentum strategy, mechanical rules, defined exits |
| Scope | ✅ EXP-004 proposal filed. $7,500 allocation. S&P 500 universe. |
| Pre-mortem | ✅ Whipsaw risk: HAWK_1 → Active transition can produce false signals in choppy markets. Mitigation: 2× ATR trailing stop catches whip reversals early. Position size limits damage per signal. Concentration risk: 5 positions in correlated sectors = hidden beta. Mitigation: sector diversification rule — max 2 positions per sector. |
| Readiness | ✅ Hawkes code exists. yfinance wired. Paper account funded. D-012 ledger active. |
| Gate | PENDING WILL APPROVAL — Standard tier requires EC + Will sign-off per desk gate structure |

**⚡ REQUIRES WILL APPROVAL before deployment. Standard tier ($5-20K) — EC protocol complete, gate is Will.**
