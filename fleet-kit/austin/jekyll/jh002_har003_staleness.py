#!/usr/bin/env python3
"""
JH-002 — HAR-003 Staleness Check

Jekyll assertion: if the HAR-003 wiki synthesis (our canonical system truth)
hasn't been modified in >48 hours, this test FAILS.

This is the feedback mechanism. Instead of building wires from every system
into the wiki, we test whether the wiki is being maintained and flag it
when it's not.

Exit codes:
  0 = PASS (HAR-003 is current)
  1 = FAIL (HAR-003 is stale or missing)
"""
import os
import sys
import time
from pathlib import Path

# Target: the canonical HAR-003 wiki synthesis
HAR003_PATH = Path.home() / "spark-vault" / "wiki" / "syntheses" / "har-003-infrastructure-as-memory.md"
STALENESS_HOURS = 48
STALENESS_SECONDS = STALENESS_HOURS * 3600

# Alternate names that would also satisfy the assertion
ALT_PATHS = [
    Path.home() / "spark-vault" / "wiki" / "syntheses" / "har-003.md",
    Path.home() / "spark-vault" / "wiki" / "entities" / "har-003.md",
    Path.home() / "spark-vault" / "projects" / "A-003" / "studies" / "HAR-003-osprey-stack-position.md",
]


def check_staleness(path: Path) -> tuple[bool, str]:
    """Returns (passes, message)."""
    if not path.exists():
        return False, f"MISSING — {path} does not exist"

    mtime = path.stat().st_mtime
    age_seconds = time.time() - mtime
    age_hours = age_seconds / 3600

    if age_seconds > STALENESS_SECONDS:
        return False, (
            f"STALE — {path.name} last modified {age_hours:.1f}h ago "
            f"(threshold: {STALENESS_HOURS}h)"
        )

    return True, f"CURRENT — {path.name} modified {age_hours:.1f}h ago (threshold: {STALENESS_HOURS}h)"


def main():
    # Check primary path first
    passes, msg = check_staleness(HAR003_PATH)

    if passes:
        print(f"✅ JH-002: HAR-003 Staleness Check\n   {msg}")
        return 0

    # Primary failed — check alternates
    for alt in ALT_PATHS:
        alt_passes, alt_msg = check_staleness(alt)
        if alt_passes:
            print(f"✅ JH-002: HAR-003 Staleness Check (via fallback)\n   {alt_msg}")
            return 0

    # All paths failed
    print(f"❌ JH-002: HAR-003 Staleness Check")
    
    # Check primary
    if not HAR003_PATH.exists():
        print(f"   PRIMARY MISSING: {HAR003_PATH}")
    else:
        _, msg = check_staleness(HAR003_PATH)
        print(f"   PRIMARY: {msg}")

    # Check alternates
    for alt in ALT_PATHS:
        if alt.exists():
            _, msg = check_staleness(alt)
            print(f"   FALLBACK: {msg}")
        else:
            print(f"   FALLBACK MISSING: {alt}")

    print(f"\n   🔧 Fix: Update HAR-003 wiki synthesis at:")
    print(f"      {HAR003_PATH}")
    print(f"   The HAR-003 study (projects/A-003/studies/HAR-003-osprey-stack-position.md)")
    print(f"   is the source of truth. Port current system state into the wiki.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
