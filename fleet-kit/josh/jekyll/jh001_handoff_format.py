#!/usr/bin/env python3
"""
Jekyll Assertion JH-001 — Handoff Format Compliance

Tests that handoffs in the QM inbox are valid JSON with all required fields.
Catches markdown handoffs before they reach QM processor and fail validation.

Source: RC-20260519-handoff-format-enforcement (Forge recommendation)
Pack: G (Cron/Infrastructure Safety) — or standalone JH assertion

Usage:
    python3 jh001_handoff_format.py                    # Check all
    python3 jh001_handoff_format.py --inbox-path <dir>  # Custom path
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPARK_VAULT = Path.home() / "spark-vault"
INBOX_REAL = SPARK_VAULT / "handoffs" / "inbox" / "real"

REQUIRED_FIELDS = ["handoff_id", "from_agent", "to_agent", "authority", "objective"]


def check_inbox(inbox_path: Path) -> dict[str, Any]:
    """Check all handoffs in inbox for format compliance."""
    results: list[dict] = []
    passed = 0
    failed = 0

    for f in sorted(inbox_path.glob("*.json")):
        if f.name.startswith("SCOPE-") or f.name.startswith("RECEIPT-") or f.name.startswith("TRACE-"):
            continue  # Skip scope packets, receipts, traces
        if f.name.startswith("."):
            continue

        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            results.append({
                "file": f.name,
                "test_result": "FAIL",
                "error": "Not valid JSON",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed += 1
            continue

        # Only check files that look like handoffs (have handoff_id)
        if "handoff_id" not in data:
            continue

        missing = [rf for rf in REQUIRED_FIELDS if rf not in data or not data[rf]]
        if missing:
            results.append({
                "file": f.name,
                "handoff_id": data.get("handoff_id", "?"),
                "test_result": "FAIL",
                "error": f"Missing fields: {', '.join(missing)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed += 1
        else:
            results.append({
                "file": f.name,
                "handoff_id": data["handoff_id"],
                "from_agent": data["from_agent"],
                "to_agent": data["to_agent"],
                "authority": data["authority"],
                "test_result": "PASS",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            passed += 1

    # Also check for .md files in the inbox (shouldn't exist)
    md_files = list(inbox_path.glob("*.md"))
    md_handoffs = [f for f in md_files if not f.name.startswith("RECEIPT-")]
    if md_handoffs:
        results.append({
            "file": "MULTIPLE" if len(md_handoffs) > 1 else md_handoffs[0].name,
            "test_result": "FAIL",
            "error": f"Markdown files in inbox: {len(md_handoffs)}. Handoffs must be JSON.",
            "detail": [str(f.name) for f in md_handoffs[:5]],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        failed += len(md_handoffs)

    return {
        "assertion": "JH-001",
        "name": "Handoff Format Compliance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": passed + failed, "passed": passed, "failed": failed},
        "overall": "PASS" if failed == 0 else "FAIL",
        "results": results,
    }


def main():
    inbox = INBOX_REAL
    if "--inbox-path" in sys.argv:
        idx = sys.argv.index("--inbox-path")
        inbox = Path(sys.argv[idx + 1])

    result = check_inbox(inbox)
    passed = result["summary"]["passed"]
    failed = result["summary"]["failed"]

    if failed == 0:
        print(f"✅ JH-001 PASS: {passed} handoffs valid")
    else:
        print(f"❌ JH-001 FAIL: {passed} valid, {failed} invalid")
        for r in result["results"]:
            if r["test_result"] == "FAIL":
                print(f"   ✗ {r['file']}: {r.get('error', '?')}")

    print(f"\n---STRUCTURED_OUTPUT_START---")
    print(json.dumps(result, indent=2))
    print(f"---STRUCTURED_OUTPUT_END---")

    sys.exit(0 if result["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
