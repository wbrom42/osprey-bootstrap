#!/usr/bin/env python3
"""Scope Creep Gate — detects gradual authority expansion across scope amendments.

Pack F / F09 gap closure. Monitors scope packet amendments for:
  - Expanding allowed_paths over sequential revisions
  - Increasing authority_tier without explicit re-approval
  - Amendment frequency (more than 2 amendments in 24h)
  - Path expansion pattern (creeping toward forbidden territory)

Closes: Pack F scenario F09 (gate_scope_creep).

Usage:
    # Register a scope amendment
    python3 scope_creep_gate.py --register \
        --packet-id SCOPE-xxx \
        --field allowed_paths \
        --old-value '["~/safe/"]' \
        --new-value '["~/safe/", "~/questionable/"]'

    # Audit a packet's amendment history
    python3 scope_creep_gate.py --audit --packet-id SCOPE-xxx

    # Check creep risk for a proposed amendment
    python3 scope_creep_gate.py --check --packet-id SCOPE-xxx \
        --field allowed_paths --new-value '["~/safe/", "/etc/"]'

Exit codes:
    0 = AMENDMENT_ALLOWED (no creep detected)
    1 = AMENDMENT_BLOCKED (creep pattern detected)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_DIR = Path.home() / ".osprey" / "scope_audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

MAX_AMENDMENTS_PER_24H = 2
CREEP_WINDOW_HOURS = 24


def _audit_file(packet_id: str) -> Path:
    safe_id = packet_id.replace("/", "_").replace("..", "_")
    return AUDIT_DIR / f"{safe_id}.jsonl"


def load_audit(packet_id: str) -> list[dict[str, Any]]:
    """Load amendment history for a scope packet."""
    fpath = _audit_file(packet_id)
    if not fpath.exists():
        return []
    entries = []
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def register_amendment(packet_id: str, field: str,
                       old_value: str, new_value: str,
                       amended_by: str = "unknown") -> dict[str, Any]:
    """Register a scope packet amendment and check for creep."""
    ts = datetime.now(timezone.utc)
    history = load_audit(packet_id)

    entry = {
        "packet_id": packet_id,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "amended_by": amended_by,
        "timestamp": ts.isoformat(),
    }

    # ── Creep Detection ───────────────────────────────────────

    violations: list[str] = []
    creep_risk = "LOW"

    # 1. Amendment frequency check
    recent = [
        h for h in history
        if (ts - datetime.fromisoformat(h["timestamp"])).total_seconds() < CREEP_WINDOW_HOURS * 3600
    ]
    amendment_count = len(recent)
    if amendment_count >= MAX_AMENDMENTS_PER_24H:
        violations.append(
            f"AMENDMENT_FREQUENCY: {amendment_count + 1} amendments in 24h "
            f"(max {MAX_AMENDMENTS_PER_24H})"
        )
        creep_risk = "HIGH"

    # 2. Allowed paths expansion check
    if field == "allowed_paths":
        try:
            old_paths = set(json.loads(old_value) if isinstance(old_value, str) else old_value)
            new_paths = set(json.loads(new_value) if isinstance(new_value, str) else new_value)
        except (json.JSONDecodeError, TypeError):
            old_paths = {old_value}
            new_paths = {new_value}

        added = new_paths - old_paths
        if added:
            # Check if any new path touches sensitive areas
            sensitive = ["/etc/", "/root/", "~/.ssh", "~/.gnupg", "~/.openclaw/",
                        "/var/log/", "/proc/", "/sys/", "/boot/", "/usr/bin/", "/sbin/"]
            for p in added:
                p_expanded = str(Path(p).expanduser())
                for s in sensitive:
                    if p_expanded.startswith(os.path.expanduser(s)):
                        violations.append(
                            f"SENSITIVE_PATH: '{p}' resolves into sensitive area '{s}'"
                        )
                        creep_risk = "HIGH"
                        break

            # Track progression — are paths creeping toward forbidden territory?
            forbidden_patterns = ["/etc/", "/root/", "/var/log/", "~/.ssh", "~/.gnupg",
                                 "/proc/", "/sys/", "/boot/"]
            for p in added:
                for fp in forbidden_patterns:
                    if fp in str(p):
                        violations.append(
                            f"PATH_CREEP: '{p}' expands toward forbidden territory '{fp}'"
                        )
                        creep_risk = max(creep_risk, "HIGH")

            # Sequential expansion pattern
            prior_additions: list[str] = []
            for h in history:
                if h["field"] == "allowed_paths":
                    try:
                        h_old = set(json.loads(h["old_value"]))
                        h_new = set(json.loads(h["new_value"]))
                        prior_additions.extend(h_new - h_old)
                    except (json.JSONDecodeError, TypeError):
                        pass

            if len(prior_additions) >= 2 and len(added) > 0:
                creep_risk = max(creep_risk, "MEDIUM")
                violations.append(
                    f"SEQUENTIAL_EXPANSION: {len(prior_additions)} prior path additions "
                    f"in audit history — cumulative expansion pattern"
                )

    # 3. Authority tier escalation
    if field == "authority_tier":
        tier_order = {"OBSERVE_ONLY": 1, "BOUNDED": 2, "APPROVED_PENDING": 3,
                      "AUTO": 3, "WILL_APPROVED": 4}
        old_rank = tier_order.get(old_value, 0)
        new_rank = tier_order.get(new_value, 0)
        if new_rank > old_rank:
            violations.append(
                f"AUTHORITY_ESCALATION: authority_tier {old_value} -> {new_value} "
                f"without re-approval"
            )
            creep_risk = "HIGH"

    # 4. Cumulative amendment count (all time)
    if len(history) > 4:
        violations.append(
            f"CUMULATIVE_AMENDMENTS: {len(history)} total amendments — "
            f"packet may need re-scoping rather than further amendments"
        )
        creep_risk = max(creep_risk, "MEDIUM")

    blocked = len(violations) > 0

    # Append to audit log
    entry["violations"] = violations
    entry["creep_risk"] = creep_risk
    entry["blocked"] = blocked
    entry["amendment_count_24h"] = amendment_count
    entry["total_amendments"] = len(history) + 1

    with open(_audit_file(packet_id), "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return entry


def audit_packet(packet_id: str) -> dict[str, Any]:
    """Full audit of a scope packet's amendment history."""
    history = load_audit(packet_id)
    if not history:
        return {
            "packet_id": packet_id,
            "total_amendments": 0,
            "amendments": [],
            "creep_detected": False,
            "risk_level": "NONE",
        }

    violations_found = []
    risk_level = "LOW"
    for h in history:
        for v in h.get("violations", []):
            violations_found.append({"timestamp": h["timestamp"], "violation": v})
        h_risk = h.get("creep_risk", "LOW")
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        if risk_order.get(h_risk, 0) > risk_order.get(risk_level, 0):
            risk_level = h_risk

    return {
        "packet_id": packet_id,
        "total_amendments": len(history),
        "first_amendment": history[0]["timestamp"] if history else None,
        "last_amendment": history[-1]["timestamp"] if history else None,
        "amendments": history,
        "violations": violations_found,
        "creep_detected": len(violations_found) > 0,
        "risk_level": risk_level,
    }


def check_amendment(packet_id: str, field: str, new_value: str) -> dict[str, Any]:
    """Pre-flight check: would this amendment trigger creep detection?"""
    # Dry run — don't save
    history = load_audit(packet_id)
    old_value = history[-1]["new_value"] if history else "[]"

    # Run detection logic (read-only)
    violations = []
    creep_risk = "LOW"

    if field == "allowed_paths":
        try:
            old_paths = set(json.loads(old_value))
            new_paths = set(json.loads(new_value))
        except (json.JSONDecodeError, TypeError):
            old_paths = {old_value}
            new_paths = {new_value}

        added = new_paths - old_paths
        sensitive = ["/etc/", "/root/", "~/.ssh", "~/.gnupg", "~/.openclaw/",
                    "/var/log/", "/proc/", "/sys/", "/boot/"]
        for p in added:
            p_expanded = str(Path(p).expanduser())
            for s in sensitive:
                if p_expanded.startswith(os.path.expanduser(s)):
                    violations.append(f"SENSITIVE_PATH: '{p}' into '{s}'")
                    creep_risk = "HIGH"

    if field == "authority_tier":
        tier_order = {"OBSERVE_ONLY": 1, "BOUNDED": 2, "APPROVED_PENDING": 3,
                      "AUTO": 3, "WILL_APPROVED": 4}
        old_rank = tier_order.get(old_value, 0)
        new_rank = tier_order.get(new_value, 0)
        if new_rank > old_rank:
            violations.append(f"AUTHORITY_ESCALATION: {old_value} -> {new_value}")

    recent = [
        h for h in history
        if (datetime.now(timezone.utc) - datetime.fromisoformat(h["timestamp"])).total_seconds()
        < CREEP_WINDOW_HOURS * 3600
    ]
    if len(recent) >= MAX_AMENDMENTS_PER_24H:
        violations.append(f"AMENDMENT_FREQUENCY: {len(recent)} in 24h")

    return {
        "packet_id": packet_id,
        "field": field,
        "new_value": new_value,
        "would_block": len(violations) > 0,
        "violations": violations,
        "risk": creep_risk,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scope Creep Gate")
    parser.add_argument("--register", action="store_true", help="Register a scope amendment")
    parser.add_argument("--audit", action="store_true", help="Audit amendment history")
    parser.add_argument("--check", action="store_true", help="Pre-flight check")
    parser.add_argument("--packet-id", required=True, help="Scope packet ID")
    parser.add_argument("--field", help="Field being amended")
    parser.add_argument("--old-value", help="Previous value")
    parser.add_argument("--new-value", help="New value")
    parser.add_argument("--amended-by", default="unknown", help="Who made the amendment")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    if args.register:
        if not args.field or args.old_value is None or args.new_value is None:
            print("ERROR: --register requires --field, --old-value, --new-value", file=sys.stderr)
            sys.exit(2)
        result = register_amendment(
            packet_id=args.packet_id,
            field=args.field,
            old_value=args.old_value,
            new_value=args.new_value,
            amended_by=args.amended_by,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            verdict = "❌ BLOCKED" if result["blocked"] else "✅ ALLOWED"
            print(f"{verdict}: Amendment to {args.packet_id}.{args.field}")
            print(f"  Risk: {result['creep_risk']}")
            print(f"  Amendments in 24h: {result['amendment_count_24h']}")
            print(f"  Total amendments: {result['total_amendments']}")
            for v in result.get("violations", []):
                print(f"  ⚠️  {v}")
        sys.exit(1 if result["blocked"] else 0)

    elif args.audit:
        result = audit_packet(args.packet_id)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Audit: {result['packet_id']}")
            print(f"  Amendments: {result['total_amendments']}")
            print(f"  Risk level: {result['risk_level']}")
            print(f"  Creep detected: {result['creep_detected']}")
            if result["violations"]:
                print(f"  Violations:")
                for v in result["violations"]:
                    print(f"    ⚠️  [{v['timestamp']}] {v['violation']}")
            if result["amendments"]:
                print(f"  History:")
                for a in result["amendments"][-5:]:
                    print(f"    {a['timestamp'][:19]} | {a['field']}: {a['old_value'][:30]} -> {a['new_value'][:30]}")
        sys.exit(1 if result["creep_detected"] else 0)

    elif args.check:
        if not args.field or args.new_value is None:
            print("ERROR: --check requires --field and --new-value", file=sys.stderr)
            sys.exit(2)
        result = check_amendment(args.packet_id, args.field, args.new_value)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            verdict = "❌ WOULD BLOCK" if result["would_block"] else "✅ WOULD ALLOW"
            print(f"{verdict}: {args.packet_id}.{args.field} -> {args.new_value}")
            print(f"  Risk: {result['risk']}")
            for v in result["violations"]:
                print(f"  ⚠️  {v}")
        sys.exit(1 if result["would_block"] else 0)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
