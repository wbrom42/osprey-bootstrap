#!/usr/bin/env python3
"""
JH-003 — Cron Fleet Health Check

Jekyll assertion: scans the OpenClaw cron store (~/.openclaw/cron/jobs.json)
and fails if any cron has been disabled for >24h (indicating unintentional
disabling from a credential sweep or similar event).

This is the structural fix for the D-018 sweep problem. Instead of relying
on someone remembering to re-enable crons, Jekyll yells when a cron stays
off too long.

Exit codes:
  0 = PASS (all crons healthy, or legitimately paused <24h)
  1 = FAIL (crons disabled >24h found)
"""
import json
import sys
import time
from pathlib import Path

CRON_STORE = Path.home() / ".openclaw" / "cron" / "jobs.json"
STALE_HOURS = 24
STALE_SECONDS = STALE_HOURS * 3600

# Crons that are intentionally disabled (exclusions)
ALLOW_DISABLED = {
    "atlas-v1-pilot-scanner",
    "atlas-v1-pilot-monitor",
    "spend-spike-alerter",
}


def main() -> int:
    if not CRON_STORE.exists():
        print(f"❌ JH-003: CRON HEALTH CHECK\n   Cron store not found: {CRON_STORE}")
        return 1

    data = json.loads(CRON_STORE.read_text())
    jobs = data.get("jobs", [])
    now_ms = int(time.time() * 1000)

    stale_disabled = []

    for j in jobs:
        name = j.get("name", "?")
        enabled = j.get("enabled", False)

        if enabled:
            continue
        if name in ALLOW_DISABLED:
            continue

        # Determine how long it's been disabled
        # Use updatedAtMs as closest proxy for when it was disabled
        updated_ms = j.get("updatedAtMs", 0)
        age_hours = (now_ms - updated_ms) / 3600000

        if age_hours > STALE_HOURS:
            sched = j.get("schedule", {}).get("expr", "?")
            last_run = j.get("state", {}).get("lastRunAtMs", 0)
            if last_run:
                last_run_age = (now_ms - last_run) / 3600000
            else:
                last_run_age = -1

            stale_disabled.append({
                "name": name,
                "age_hours": round(age_hours, 1),
                "schedule": sched,
                "last_run_age_hours": round(last_run_age, 1) if last_run > 0 else "never"
            })

    if not stale_disabled:
        print(f"✅ JH-003: Cron Fleet Health Check — {len(jobs)} jobs, 0 stale-disabled")
        return 0

    print(f"❌ JH-003: Cron Fleet Health Check — {len(stale_disabled)} cron(s) disabled >{STALE_HOURS}h")
    for c in stale_disabled:
        last = f"last run {c['last_run_age_hours']}h ago" if c['last_run_age_hours'] != 'never' else "never ran"
        print(f"   🔴 {c['name']} — disabled {c['age_hours']}h, schedule: {c['schedule']}, {last}")

    print(f"\n   🔧 Fix: openclaw cron enable <id>")
    print(f"   Or add to ALLOW_DISABLED in jh003_cron_health.py if intentionally paused")
    return 1


if __name__ == "__main__":
    sys.exit(main())
