#!/usr/bin/env python3
"""
Pack G — Control Surface Boundary Tests

Jekyll Pack B/C expansion tests for the War Department Control Surface.
Each test returns: (test_name, passed, message)

Usage:
    python3 pack_g_control_surface.py --list
    python3 pack_g_control_surface.py --run

Exit code:
    0 — all tests pass
    1 — one or more tests fail, or invalid CLI usage
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable


PACK_NAME = "G_control_surface"
PACK_VERSION = "1.0"

REQUIRED_REGISTRY_FIELDS = {
    "agent_id",
    "pid",
    "authority_tier",
    "risk_tier_max",
    "allowed_paths",
    "forbidden_actions",
}
ALLOWED_AUTHORITY_TIERS = {"BOUNDED", "UNBOUNDED", "OBSERVE_ONLY"}
ALLOWED_RISK_TIERS = {"READ", "MUTATE", "DESTROY"}

REQUIRED_TRUTH_SECTIONS = {
    "System Overview",
    "Tested Commands",
    "Known Failures",
    "Trust Boundaries",
    "Rollback Steps",
}

SENSITIVE_PATH_PATTERNS = [
    "/etc/systemd/",
    "/etc/systemd/user/",
    "~/.openclaw/config.yaml",
    "scope packet",
    "access registry",
    "merge bouncer",
    "cron job definitions",
    "crontab",
    "timers",
    "trading system files",
    "broker integration code",
    "order execution",
    "event store database files",
    "sqlite/postgres/mysql database files",
    "append-only logs used as source-of-truth state",
]

REQUIRED_REVIEW_PACKET_FIELDS = {
    "packet_id",
    "change_summary",
    "files_changed",
    "risk_classification",
    "test_evidence",
    "decision",
}
ALLOWED_MERGE_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ALLOWED_DECISIONS = {"APPROVED", "REJECTED", "PENDING_CHANGES"}

SAMPLE_REGISTRY_ENTRY: dict[str, Any] = {
    "agent_id": "jekyll",
    "pid": "A-003",
    "authority_tier": "BOUNDED",
    "risk_tier_max": "MUTATE",
    "allowed_paths": ["/home/infinitespark2/spark-vault/projects/A-003/control-surface/"],
    "forbidden_actions": ["Merge, deploy, or run production commands."],
}

SAMPLE_TRUTH_FOLDER = """# A-003 Truth Folder

last_updated: 2026-05-20
review_cadence: weekly

## 1. System Overview
Current system overview.

## 2. Tested Commands
Commands and evidence.

## 3. Known Failures
Known failures and workarounds.

## 4. Trust Boundaries
Read/write/no-go boundaries.

## 5. Rollback Steps
Safe rollback procedure.
"""

SAMPLE_REVIEW_PACKET: dict[str, Any] = {
    "packet_id": "MB-20260520-A003-control-surface-v01",
    "change_summary": "Docs/tests-only Control Surface validation expansion.",
    "files_changed": [
        {
            "path": "projects/jekyll-agent/pack_g_control_surface.py",
            "change_type": "ADDED",
            "risk": "LOW",
            "sensitive_match": False,
        }
    ],
    "risk_classification": "LOW",
    "test_evidence": [{"command_or_check": "python3 pack_g_control_surface.py --run", "result": "PASS"}],
    "decision": "PENDING_CHANGES",
}


def result_ok(name: str, message: str) -> tuple[str, bool, str]:
    return name, True, message


def result_error(name: str, exc: Exception) -> tuple[str, bool, str]:
    return name, False, str(exc)


def has_section(markdown: str, section_name: str) -> bool:
    needle = section_name.lower()
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("#").strip().lower()
        # Accept "1. System Overview" and "System Overview" headings.
        if stripped == needle or stripped.endswith(f". {needle}"):
            return True
    return False


def extract_last_updated(markdown: str) -> str | None:
    for line in markdown.splitlines():
        lower = line.lower().strip()
        if lower.startswith("last_updated:") or lower.startswith("last updated:"):
            return line.split(":", 1)[1].strip().strip("`\"'")
    return None


# ── Registry Tests (Pack B — Classification) ──────────────────────────────

def test_registry_entry_fields() -> tuple[str, bool, str]:
    name = "test_registry_entry_fields"
    try:
        missing = sorted(REQUIRED_REGISTRY_FIELDS - SAMPLE_REGISTRY_ENTRY.keys())
        assert not missing, f"missing required registry field(s): {missing}"
        return result_ok(name, "registry entry contains all required fields")
    except Exception as exc:
        return result_error(name, exc)


def test_registry_authority_tiers() -> tuple[str, bool, str]:
    name = "test_registry_authority_tiers"
    try:
        tier = SAMPLE_REGISTRY_ENTRY["authority_tier"]
        assert tier in ALLOWED_AUTHORITY_TIERS, f"invalid authority_tier: {tier!r}"
        return result_ok(name, f"authority_tier {tier!r} is allowed")
    except Exception as exc:
        return result_error(name, exc)


def test_registry_risk_tiers() -> tuple[str, bool, str]:
    name = "test_registry_risk_tiers"
    try:
        tier = SAMPLE_REGISTRY_ENTRY["risk_tier_max"]
        assert tier in ALLOWED_RISK_TIERS, f"invalid risk_tier_max: {tier!r}"
        return result_ok(name, f"risk_tier_max {tier!r} is allowed")
    except Exception as exc:
        return result_error(name, exc)


# ── Truth Folder Tests (Pack B) ────────────────────────────────────────────

def test_truth_folder_required_sections() -> tuple[str, bool, str]:
    name = "test_truth_folder_required_sections"
    try:
        missing = sorted(section for section in REQUIRED_TRUTH_SECTIONS if not has_section(SAMPLE_TRUTH_FOLDER, section))
        assert not missing, f"missing required truth-folder section(s): {missing}"
        return result_ok(name, "truth folder contains required sections")
    except Exception as exc:
        return result_error(name, exc)


def test_truth_folder_review_date() -> tuple[str, bool, str]:
    name = "test_truth_folder_review_date"
    try:
        raw = extract_last_updated(SAMPLE_TRUTH_FOLDER)
        assert raw, "last_updated metadata is missing"
        parsed = date.fromisoformat(raw)
        return result_ok(name, f"last_updated is parseable: {parsed.isoformat()}")
    except Exception as exc:
        return result_error(name, exc)


# ── Merge Bouncer Tests (Pack C — Domain Isolation) ────────────────────────

def test_merge_bouncer_sensitive_paths() -> tuple[str, bool, str]:
    name = "test_merge_bouncer_sensitive_paths"
    try:
        haystack = "\n".join(SENSITIVE_PATH_PATTERNS).lower()
        required_coverage = {
            "systemd": ["/etc/systemd"],
            "openclaw_config": ["~/.openclaw/config.yaml"],
            "scope_packets": ["scope packet"],
            "cron_defs": ["cron", "crontab", "timer"],
            "trading_files": ["trading", "broker", "order execution"],
            "event_store": ["event store", "database", "append-only"],
        }
        missing = []
        for label, alternatives in required_coverage.items():
            if not any(needle in haystack for needle in alternatives):
                missing.append(label)
        assert not missing, f"sensitive path coverage missing: {missing}"
        return result_ok(name, "sensitive path list covers required Control Surface patterns")
    except Exception as exc:
        return result_error(name, exc)


def test_merge_bouncer_required_fields() -> tuple[str, bool, str]:
    name = "test_merge_bouncer_required_fields"
    try:
        missing = sorted(REQUIRED_REVIEW_PACKET_FIELDS - SAMPLE_REVIEW_PACKET.keys())
        assert not missing, f"missing required review-packet field(s): {missing}"
        return result_ok(name, "review packet contains required fields")
    except Exception as exc:
        return result_error(name, exc)


def test_merge_bouncer_risk_levels() -> tuple[str, bool, str]:
    name = "test_merge_bouncer_risk_levels"
    try:
        risk = SAMPLE_REVIEW_PACKET["risk_classification"]
        assert risk in ALLOWED_MERGE_RISK_LEVELS, f"invalid risk_classification: {risk!r}"
        return result_ok(name, f"risk_classification {risk!r} is allowed")
    except Exception as exc:
        return result_error(name, exc)


def test_merge_bouncer_decision_values() -> tuple[str, bool, str]:
    name = "test_merge_bouncer_decision_values"
    try:
        decision = SAMPLE_REVIEW_PACKET["decision"]
        assert decision in ALLOWED_DECISIONS, f"invalid decision: {decision!r}"
        return result_ok(name, f"decision {decision!r} is allowed")
    except Exception as exc:
        return result_error(name, exc)


TESTS: list[Callable[[], tuple[str, bool, str]]] = [
    test_registry_entry_fields,
    test_registry_authority_tiers,
    test_registry_risk_tiers,
    test_truth_folder_required_sections,
    test_truth_folder_review_date,
    test_merge_bouncer_sensitive_paths,
    test_merge_bouncer_required_fields,
    test_merge_bouncer_risk_levels,
    test_merge_bouncer_decision_values,
]


def list_tests() -> int:
    for test in TESTS:
        print(test.__name__)
    return 0


def run_tests() -> int:
    print(f"Jekyll Pack G — Control Surface Boundary Tests ({PACK_NAME} v{PACK_VERSION})")
    print(f"Total tests: {len(TESTS)}")
    print()

    results = [test() for test in TESTS]
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed

    for test_name, ok, message in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status:<5} {test_name} — {message}")

    print()
    print(f"Summary: {passed}/{len(results)} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/list Control Surface Pack B/C expansion tests.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="list test names")
    group.add_argument("--run", action="store_true", help="run tests")
    args = parser.parse_args(argv)

    if args.list:
        return list_tests()
    # Default to --run so the file behaves like the existing Jekyll packs.
    return run_tests()


if __name__ == "__main__":
    sys.exit(main())
