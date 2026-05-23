# Osprey Fleet Instance — {{TARGET}}

Deployed from father (spark-5911) on 2026-05-19.

## Systems Included
- **Trading:** D-013 thesis pipeline (classify → thesis → adversarial → judge → veto → size → paper)
- **Jekyll:** Behavioral safety (6 assertion packs, 116 scenarios)
- **Forge:** Improvement loop + enforcement gates
- **Security:** War Department credential sweeps + ABOM
- **Academy:** Research pipeline + M-001 monthly discovery

## Setup
1. Run `bash bin/setup.sh`
2. Configure secrets (Alpaca keys if trading)
3. Run `bash bin/daily-pulse.sh` to verify health
4. Run `cd jekyll && bash run-jekyll.sh` to verify safety

## Fleet Wiki
Findings surface to the shared memory wiki. Patterns that appear across
2+ instances get priority.
