# Bottleneck Radar — Signal Database & Brief Generator

**PID:** I-001 (proposed Tier 3)

## Directory Structure

```
radar/
├── config/
│   ├── bottlenecks.yaml    # 10 bottlenecks with scoring inputs
│   ├── companies.yaml      # 14 tracked public companies
│   ├── theses.yaml         # 3 working hypotheses
│   ├── tripwires.yaml      # 5 operational tripwires
│   └── sources.yaml        # (future) automated source configs
├── data/
│   ├── radar.sqlite        # Main database
│   ├── raw/                # (future) downloaded source documents
│   └── exports/            # CSV exports
├── sql/
│   └── schema.sql          # 12-table SQLite schema
├── scripts/
│   ├── init_db.py          # Create + seed database
│   ├── import_manual_signals.py  # Import from CSV
│   ├── score_bottlenecks.py      # Compute weekly scores
│   └── generate_weekly_brief.py  # Produce brief from DB
├── templates/              # (future) Jinja2 templates
├── briefs/                 # Generated weekly briefs
├── .env.example
└── requirements.txt
```

## Quick Start

```bash
# Initialize fresh database with seeds
.venv/bin/python scripts/init_db.py --db data/radar.sqlite

# Import manual signals from CSV
.venv/bin/python scripts/import_manual_signals.py --csv ../manual-signal-log-fixed.csv --db data/radar.sqlite

# Compute weekly bottleneck scores
.venv/bin/python scripts/score_bottlenecks.py --db data/radar.sqlite --week 2026W19

# Generate weekly brief
.venv/bin/python scripts/generate_weekly_brief.py --db data/radar.sqlite --week 2026W19 --out briefs/weekly-2026W19.md
```

## The Brief-as-Query Test

The Friday brief must be producible from 5 SQL queries:
1. `SELECT ... FROM signals WHERE pass_id LIKE` — signal log by pass
2. `SELECT ... FROM bottleneck_scores WHERE week_id` — bottleneck scoreboard
3. `SELECT ... FROM signal_thesis_impacts` — thesis disconfirmation review
4. `SELECT ... FROM null_searches` — anti-prompt log
5. `SELECT ... FROM tripwire_checks` — tripwire panel

## Schema (12 tables)

- **theses** — 3 working hypotheses
- **bottlenecks** — 10 scarcity bottlenecks
- **signals** — atomic evidence units
- **signal_thesis_impacts** — signal ↔ thesis grading
- **sources** — URL metadata with tier
- **signal_sources** — signal ↔ source join per H-007
- **bottleneck_scores** — weekly score snapshots
- **null_searches** — disconfirming anti-prompts
- **tripwires** — operational triggers
- **tripwire_checks** — weekly tripwire status
- **passes** — collection runs
- **signal_revisions** — audit trail (no deletes)

## Current Status (2026W19)

- 13 signals imported (12 ACCEPTED, 1 WATCHLIST)
- 10 bottlenecks scored (2 EVIDENCE, 8 PRIOR_UNREFRESHED)
- See `briefs/weekly-2026W19-from-db.md`

## Phase 3 Operations

Phase 3 adds recurring delivery and decision surfaces around the DB:

- **Friday Brief:** `scripts/generate_weekly_brief.py` now includes an Executive Focus top-3 section and weekly recommended actions. Run after scoring:
  ```bash
  .venv/bin/python scripts/score_bottlenecks.py --db data/radar.sqlite --week YYYYWww
  .venv/bin/python scripts/generate_weekly_brief.py --db data/radar.sqlite --week YYYYWww --out briefs/weekly-YYYYWww-friday.md
  ```
- **Alerts:** `scripts/alert-engine.py` and `scripts/focus-promoter.py` are intended to run from Hermes cron (`i001-alert-engine`, `i001-focus-promoter`) and guard against stale upstream scores.
- **Quadrant:** `scripts/quadrant_view.py` renders the Urgency x Impact matrix.
  ```bash
  .venv/bin/python scripts/quadrant_view.py --db data/radar.sqlite --out data/exports/quadrant-YYYYWww.md
  ```
- **Ticker Snapshot:** `scripts/ticker_snapshot.py` emits the daily latest-readings rail.
  ```bash
  .venv/bin/python scripts/ticker_snapshot.py --db data/radar.sqlite --out data/exports/ticker-YYYY-MM-DD.md
  ```
- **Exit Gate:** `docs/exit-gate-policy.md` defines retire-never-delete policy; `scripts/exit_gate_report.py` produces non-destructive review packets.
  ```bash
  .venv/bin/python scripts/exit_gate_report.py --db data/radar.sqlite --out data/exports/exit-gate-YYYY-MM-DD.md
  ```
