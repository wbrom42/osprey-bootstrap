# D-019 Deployment Status

Processed HH-20260521-Spock-Hermes-D019-EXP-DEPLOY.

## EXP-002 CBRS
- Proposal read path: `projects/D-019/proposals/EXP-002-cbrs-cerebras-entry.md`
- Existing state file: `projects/D-019/exp002_state.json`
- Required next build: wire `~/.hermes/scripts/cbrs-position-monitor.py` starter-zone signal to Alpaca Paper Account3 order execution within $5K allocation.
- Current status: HOLD for verified paper account credentials/session and order-execution smoke test. No live/paper order placed in this cron run.

## EXP-004 Hawkes Regime Momentum
- Proposal read path: `projects/D-019/proposals/EXP-004-hawkes-regime-momentum.md`
- Required next build: port crypto Hawkes state machine to S&P 500 daily yfinance scan; enforce 2% allocation, max 5 concurrent, sector cap 2, ATR and hard stops; route signals to Alpaca Paper.
- Current status: BUILD QUEUED; not completed inside 15-minute relay window.

## EXP-003/EXP-005
- Track only in D-012; no capital deployment.

Risk note: paper trading is still an external side effect. This relay did not place orders without verifying Alpaca Paper Account3 credentials and kill-switch state.
