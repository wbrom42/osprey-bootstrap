#!/usr/bin/env python3
"""
JH-006 — Doctrine Pointer Staleness Check

Jekyll assertion: every doctrine file referenced in STARTUP_CONTEXT.md
must have been modified within its declared staleness window.

JH-002 already checks HAR-003 specifically. This test generalizes the
pattern: it reads the YAML frontmatter of STARTUP_CONTEXT.md, finds every
doctrine file pointer, reads EACH target file's own frontmatter for
`last_reviewed` and `stale_after`, and flags any that have expired.

This catches memory drift at the pointer level: if HEARTBEAT.md says its
own last_reviewed is 8 days ago with a 7d staleness, we flag it.

DETECT_REPORT_ONLY. Lane A. Never mutates.

Exit codes:
  0 = PASS (all doctrine pointers are current)
  1 = FAIL (one or more doctrine files are stale or missing staleness metadata)
"""
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SPARK_VAULT = Path.home() / "spark-vault"
STARTUP_CONTEXT = SPARK_VAULT / "STARTUP_CONTEXT.md"

# Files to check. Each entry: (field_name_in_startup_context, fallback_staleness_days, description)
DOCTRINE_TARGETS = [
    # Field name                     Default staleness  Label
    ("current_doctrine_file",        7,                 "OSPREY_CONSTITUTION.md"),
    ("current_heartbeat_file",       7,                 "HEARTBEAT.md"),
    ("current_memory_file",          7,                 "MEMORY.md"),
    ("current_soul_file",            30,                "SOUL.md"),
    ("current_identity_file",        30,                "IDENTITY.md"),
    ("current_user_file",            30,                "USER.md"),
    ("current_operating_manual",     14,                "OSPREY_OPERATING_MANUAL.md"),
    ("current_projects_index",       7,                 "Projects Index"),
    ("supersession_registry",        14,                "Supersession Registry"),
]


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
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = value
    return result


def extract_file_yaml(path: Path) -> dict:
    """Extract YAML frontmatter from any file that has it."""
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {}
    
    match = re.search(r'```yaml\n(.*?)\n```', text, re.DOTALL)
    if not match:
        return {}
    
    raw = match.group(1)
    result = {}
    for line in raw.split('\n'):
        line = line.strip()
        if ':' not in line or line.startswith('#'):
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = value
    return result


def resolve_path(raw_value: str) -> Path | None:
    """Resolve a doctrine pointer to an absolute path."""
    if not raw_value:
        return None

    # Handle compound pointers like "HEARTBEAT.md → projects-office/governance/..."
    if " → " in raw_value:
        raw_value = raw_value.split(" → ")[0].strip()

    if raw_value.startswith("~/"):
        return Path.home() / raw_value[2:]

    # Relative to spark-vault
    return SPARK_VAULT / raw_value


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


def check_file_staleness(
    path: Path, field_name: str, default_stale_days: int, label: str
) -> dict:
    """Check if a doctrine file has exceeded its staleness window."""
    result = {
        "field": field_name,
        "label": label,
        "path": str(path),
        "result": "PASS",
        "error": None,
    }

    if not path.exists():
        result["result"] = "FAIL"
        result["error"] = f"MISSING: {path}"
        return result

    # Try to read the file's own frontmatter for last_reviewed and stale_after
    file_yaml = extract_file_yaml(path)

    # Get staleness threshold: file's own stale_after takes precedence
    stale_after_days = default_stale_days
    if "stale_after" in file_yaml:
        match = re.match(r'(\d+)d', str(file_yaml["stale_after"]))
        if match:
            stale_after_days = int(match.group(1))

    # Get last reviewed date
    last_reviewed = file_yaml.get("last_reviewed", "")
    last_date = parse_date(last_reviewed)

    if last_date is None:
        # No last_reviewed in file — check file modification time
        mtime = path.stat().st_mtime
        last_date = datetime.fromtimestamp(mtime, tz=timezone.utc)
        result["source"] = "file_mtime"
    else:
        result["source"] = "frontmatter_last_reviewed"

    # Calculate staleness
    now = datetime.now(timezone.utc)
    age_days = (now - last_date).total_seconds() / 86400

    result["age_days"] = round(age_days, 1)
    result["stale_after_days"] = stale_after_days
    result["last_reviewed"] = last_date.strftime("%Y-%m-%d")

    if age_days > stale_after_days:
        result["result"] = "FAIL"
        result["error"] = (
            f"STALE: {label} last reviewed {age_days:.1f}d ago "
            f"(threshold: {stale_after_days}d)"
        )

    return result


def main() -> int:
    # Read STARTUP_CONTEXT
    if not STARTUP_CONTEXT.exists():
        print(f"❌ JH-006: Doctrine Pointer Staleness")
        print(f"   STARTUP_CONTEXT.md is MISSING — cannot check doctrine pointers")
        return 1

    sc_yaml = extract_yaml(STARTUP_CONTEXT.read_text(encoding='utf-8'))

    if not sc_yaml:
        print(f"❌ JH-006: Doctrine Pointer Staleness")
        print(f"   No YAML frontmatter in STARTUP_CONTEXT.md")
        return 1

    results = []
    for field_name, default_stale_days, label in DOCTRINE_TARGETS:
        raw_value = sc_yaml.get(field_name, "")
        if not raw_value:
            # Optional field — skip
            continue

        path = resolve_path(raw_value)
        if path is None:
            continue

        result = check_file_staleness(path, field_name, default_stale_days, label)
        results.append(result)

    # Print results
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    print(f"JH-006: Doctrine Pointer Staleness — {now_str}")
    print(f"  {'─'*50}")

    failures = []
    for r in results:
        symbol = "✅" if r["result"] == "PASS" else "❌"
        age = r.get("age_days", "?")
        threshold = r.get("stale_after_days", "?")
        src = r.get("source", "?")
        print(f"  {symbol} {r['label']} — {age}d old (limit: {threshold}d, source: {src})")
        if r["error"]:
            failures.append(r)
            print(f"     ✗ {r['error']}")

    print(f"\n  Results: {len(results) - len(failures)}/{len(results)} current, {len(failures)} stale")

    if failures:
        print(f"\n  🔧 Fix: Update the stale files and bump their last_reviewed dates.")
        for r in failures:
            print(f"     {r['label']}: {r['path']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
