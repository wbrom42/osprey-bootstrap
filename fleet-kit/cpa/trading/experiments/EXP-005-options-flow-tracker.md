# EXP-005 — Options Flow Unusual Activity (RESEARCH ONLY)

**Status:** D-012 TRACKING — No capital deployed
**Date:** 2026-05-21
**Proposed By:** Spock (S-2)

---

## Research Objective

Validate whether unusual options flow (sweep orders, block trades, OTM call accumulation) signals informed positioning before price moves. UW MCP provides raw data. D-012 tracking grades predictions without capital.

## Signal Filter

- Premium >$500K
- Volume >5× open interest
- Bullish flow (calls, call spreads, sold puts)
- Exclude: obvious hedging (protective puts on existing long positions), dealer positioning, 0DTE noise

## Tracking Metrics (D-012)

- Number of qualifying signals per week
- Directional accuracy at 5/10/21 days post-signal
- Signal return vs underlying buy-and-hold
- Theta decay impact (are returns eaten by time decay before price moves?)

## Graduation Criteria

Deploy paper capital if:
- >50% directional accuracy at 10-day horizon
- Signal return > underlying + 3% (to cover theta/spread costs)
- At least 20 graded predictions

## Known Risks

- Data latency: UW data may lag real-time — competitors with direct exchange feeds have advantage
- False positives: hedging looks like conviction, dealers repositioning looks like directional bets
- Theta: paper returns that look good on signal date erode before price confirms

## Allocation (if graduated)

$7,500 — Standard tier, EC + Will approval. Options only (no stock). Max 3% per position.
