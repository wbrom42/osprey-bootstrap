# D-013: Osprey Trading Architecture v2

## Identity
- **PID:** D-013
- **Name:** Trading Agents Portfolio Architecture
- **Pillar:** DARPA
- **Phase:** SPEC_D
- **Authority:** BOUNDED (EC protocol only)
- **Owner:** Spock (design), Hermes (EC protocol)

## Summary

A portfolio-first, quality-driven trading architecture based on the TradingAgents research pattern (arXiv:2412.20138). Replaces the old signal→execute loop with a structured thesis generation → adversarial review → judge → size → manage pipeline.

## Architecture

Three-layer design:

**Layer 1 — Thesis Generation (EC Chain)**
`CLASSIFY → THESIS → ADVERSARIAL REVIEW → JUDGE → SIZE → ACT`

**Layer 2 — Portfolio Management**
`HOLDINGS → RISK SCAN → REBALANCE`

**Layer 3 — Calibration (P-001)**
`PREDICTION → VERIFY → SCORE → FEEDBACK`

## Key Shift
|| Before | After |
|--------|--------|-------|
| UW tools | Execution signals | Research inputs |
| Signal volume | Health metric | Thesis accuracy = health |
| Time horizon | Minutes/hours | Days/weeks/months |

## Build Order (from Spock's design)
1. Adversarial review — mandatory second pass in EC chain
2. VetoEngine graduated powers — D-008 change
3. Portfolio snapshot — aggregate holdings across accounts
4. Portfolio consistency check — correlation + concentration
5. P-001 integration — auto-register theses as predictions

## References
- Design doc: `projects/D-013/design/`
- TradingAgents paper: arXiv:2412.20138
- Original handoff: HH-20260517-spock-trading-architecture-v2
