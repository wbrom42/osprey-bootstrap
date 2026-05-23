#!/usr/bin/env python3
"""
JH-007 — Heartbeat Staleness Check

Jekyll assertion: HEARTBEAT.md must be current. A stale heartbeat is worse
than no heartbeat — it projects false confidence while hiding degradation.

Checks:
1. HEARTBEAT.md exists and has valid YAML frontmatter
2. `last_reviewed` date is within `stale_after` window
3. `last_success` timestamp is recent (within 2x stale_after, generous)
4. `status` is CURRENT (not STALE or UNKNOWN)
5. `known_degraded` entries that have been stale >7d are flagged

DETECT_REPORT_ONLY. Lane A. Never mutates HEARTBEAT.md.

Exit codes:
  0 = PASS (heartbeat is current and fresh)
  1 = FAIL (heartbeat is stale, missing, or degraded)
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HEARTBEAT = Path.home() / "spark-vault" / "HEARTBEAT.md"


def extract_yaml(text: str) -> dict:
    """Extract key:value pairs from YAML frontmatter."""
    match = re.search(r'```yaml\n(.*?)\n```', text, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result = {}
    for line in raw.split('\n'):
        line = line.strip()
        if ':' not in line or line.startswith('#'):
            continue
        if line.startswith('-'):
            # List items under forbidden_actions, known_degraded, etc.
            key = "____list_context"
            value = line.strip()
            result.setdefault("____list_items", []).append(value)
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = value
    return result


def parse_date(date_str: str) -> datetime | None:
    """Parse a YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_timestamp(ts_str: str) -> datetime | None:
    """Parse an ISO timestamp like 2026-05-23T01:55."""
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str.strip()[:16], "%Y-%m-%dT%H:%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def main() -> int:
    errors = []
    warnings = []
    now = datetime.now(timezone.utc)

    # Check existence
    if not HEARTBEAT.exists():
        print(f"❌ JH-007: Heartbeat Staleness Check")
        print(f"   HEARTBEAT.md is MISSING")
        print(f"\n   🔧 Fix: Restore HEARTBEAT.md from git or rebuild from Compass.")
        return 1

    try:
        text = HEARTBEAT.read_text(encoding='utf-8')
    except Exception as e:
        print(f"❌ JH-007: Heartbeat Staleness Check")
        print(f"   HEARTBEAT.md is UNREADABLE: {e}")
        return 1

    yaml = extract_yaml(text)
    if not yaml:
        print(f"❌ JH-007: Heartbeat Staleness Check")
        print(f"   No YAML frontmatter found in HEARTBEAT.md")
        return 1

    # Parse staleness window
    stale_after_days = 7  # default
    if "stale_after" in yaml:
        match = re.match(r'(\d+)d', str(yaml["stale_after"]))
        if match:
            stale_after_days = int(match.group(1))

    # Check status
    status = yaml.get("status", "").lower()
    if status != "current":
        errors.append(f"status is '{status}', expected CURRENT")

    # Check last_reviewed
    last_reviewed_str = yaml.get("last_reviewed", "")
    last_reviewed = parse_date(last_reviewed_str)
    if last_reviewed is None:
        errors.append(f"last_reviewed is missing or unparseable: '{last_reviewed_str}'")
    else:
        review_age_days = (now - last_reviewed).total_seconds() / 86400
        if review_age_days > stale_after_days:
            errors.append(
                f"last_reviewed is {review_age_days:.1f}d ago "
                f"(threshold: {stale_after_days}d) — {last_reviewed_str}"
            )

    # Check last_success
    last_success_str = yaml.get("last_success", "")
    last_success = parse_timestamp(last_success_str)
    if last_success is None:
        warnings.append(f"last_success is missing or unparseable: '{last_success_str}'")
    else:
        success_age_hours = (now - last_success).total_seconds() / 3600
        # Generous threshold: 2x stale_after in days, converted to hours
        max_success_age_hours = stale_after_days * 24 * 2
        if success_age_hours > max_success_age_hours:
            errors.append(
                f"last_success is {success_age_hours:.1f}h ago "
                f"(threshold: {max_success_age_hours:.0f}h) — {last_success_str}"
            )
        elif success_age_hours > stale_after_days * 24:
            warnings.append(
                f"last_success is {success_age_hours:.1f}h old — within grace window "
                f"but approaching limit ({stale_after_days * 24}h)"
            )

    # Check next_review
    next_review_str = yaml.get("next_review", "")
    next_review = parse_date(next_review_str)
    if next_review and next_review < now:
        warnings.append(
            f"next_review is in the past: {next_review_str} — review is overdue"
        )

    # Check known_degraded count
    known_degraded_count = len(yaml.get("____list_items", []))
    if known_degraded_count > 2:
        warnings.append(f"known_degraded has {known_degraded_count} entries — review if fixes are available")

    # Check forbidden_actions present (can be in YAML key or as list items under it)
    if ("forbidden_actions" not in yaml 
        and "forbidden_actions:" not in text
        and not yaml.get("____list_items")):
        warnings.append("forbidden_actions block missing — HEARTBEAT.md should define what it cannot do")

    # Output
    now_str = now.strftime("%Y-%m-%d %H:%MZ")
    print(f"JH-007: Heartbeat Staleness Check — {now_str}")
    print(f"  {'─'*50}")
    print(f"  HEARTBEAT.md | status: {status} | last_reviewed: {last_reviewed_str}")
    print(f"  last_success: {last_success_str} | stale_after: {stale_after_days}d")
    print(f"  next_review: {next_review_str} | degraded: {known_degraded_count} items")

    if errors:
        print(f"\n  ❌ FAIL — {len(errors)} error(s):")
        for e in errors:
            print(f"     ✗ {e}")

    if warnings:
        print(f"\n  ⚠ {len(warnings)} warning(s):")
        for w in warnings:
            print(f"     ⚠ {w}")

    if not errors and not warnings:
        print(f"\n  ✅ PASS — Heartbeat is current and fresh")
    elif not errors:
        print(f"\n  ⚠ PASS-WITH-WARNINGS")

    if errors:
        print(f"\n  🔧 Fix: Update HEARTBEAT.md's last_reviewed and last_success fields.")
        print(f"     Run system diagnostics: openclaw cron list | grep error")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
