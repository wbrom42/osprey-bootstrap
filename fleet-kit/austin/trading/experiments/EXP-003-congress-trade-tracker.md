# EXP-003 — Congress Trade Signal Validation (RESEARCH ONLY)

**Status:** D-012 TRACKING — No capital deployed
**Date:** 2026-05-21
**Proposed By:** Spock (S-2)

---

## Research Objective

Validate whether congressional trades filtered for committee relevance + clustered timing + unusual size produce alpha over retail. If edge confirmed in 30-90 days of D-012 tracking, graduate to paper deployment (Standard tier, EC + Will).

## Signal Filter

- Committee-relevant trade (member sits on committee with jurisdiction over the company's sector)
- Trade size >$15,000
- 2+ members same stock within 30 days (clustered timing)
- Exclude: index funds, ETFs, blind trust purchases, spouse non-discretionary accounts

## Tracking Metrics (D-012)

- Number of filtered signals per 30-day window
- Directional accuracy at 30/60/90 days post-filing
- Signal return vs SPY baseline
- False positive rate (filed trades that go against member's position)

## Graduation Criteria

Deploy paper capital if:
- >55% directional accuracy at 30 days
- Signal return > SPY + 2% over tracking period
- At least 10 graded predictions in D-012

## Allocation (if graduated)

$7,500 — Standard tier, EC + Will approval.
