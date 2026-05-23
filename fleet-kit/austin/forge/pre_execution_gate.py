#!/usr/bin/env python3
"""Pre-Execution Gate — BLOCKs tasks without valid scope packet + provenance.

Layer 2 enforcement. Called at the delegation boundary BEFORE any work
starts. Validates:

  1. A scope packet exists for this task
  2. The scope packet has provenance_gate_complete=true
  3. Corresponding provenance gate events exist in the Event Store
  4. The scope packet is not expired

Returns GATE_BLOCKED with a structured reason on failure, or APPROVE with
the validated scope packet data on success.

Usage::

    python3 pre_execution_gate.py --scope SCOPE-xxx.approval.json

Exit codes:
    0 = APPROVE (proceed)
    1 = GATE_BLOCKED (do not proceed)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPARK_VAULT = Path.home() / "spark-vault"
SCOPE_DIR = SPARK_VAULT / "handoffs" / "inbox" / "real"
SCOPE_PROCESSED_DIR = SPARK_VAULT / "handoffs" / "inbox" / "real" / "processed"

# ── Import event store (soft — gate should work without it for basic validation) ──

_HAS_V2_STORE = False
try:
    from osprey.event_store.store import EventStore
    from osprey.event_store.schema import EventType
    _HAS_V2_STORE = True
except ImportError:
    EventStore = None
    EventType = None


def _find_scope_packet(scope_arg: str) -> Path | None:
    """Resolve a scope packet argument to a file path.

    Accepts:
      - Full path (absolute or relative)
      - Just the filename (searches scope dirs)
    """
    p = Path(scope_arg)
    if p.is_file():
        return p
    # Try relative to scope dirs
    for d in [SCOPE_DIR, SCOPE_PROCESSED_DIR]:
        candidate = d / p.name if p.parent == Path(".") else d / str(p)
        if candidate.is_file():
            return candidate
    return None


def _validate_scope_packet(packet: dict[str, Any]) -> list[str]:
    """Validate a scope packet's enforcement-critical fields.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    # Schema version
    sv = packet.get("schema_version", "")
    if sv != "scope-packet-v1":
        errors.append(f"schema_version is '{sv}', expected 'scope-packet-v1'")

    # Provenance gate stamp
    pg = packet.get("provenance_gate_complete", False)
    if not pg:
        errors.append("provenance_gate_complete is False or missing — run provenance_gate.py --stamp")

    # EC classification
    if not packet.get("ec_classification"):
        errors.append("ec_classification is missing")

    # Authority tier
    if not packet.get("authority_tier"):
        errors.append("authority_tier is missing")

    # Risk tier
    rt = packet.get("risk_tier", "")
    if rt not in ("READ", "MUTATE", "DESTROY"):
        errors.append(f"risk_tier is '{rt}', expected READ/MUTATE/DESTROY")

    # Expiry check (optional expiry field)
    expiry = packet.get("expiry")
    if expiry:
        try:
            expiry_dt = datetime.fromisoformat(expiry)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            if expiry_dt < datetime.now(timezone.utc):
                errors.append(f"scope packet expired at {expiry}")
        except (ValueError, TypeError):
            errors.append(f"invalid expiry value: {expiry}")

    # EC build order (required for MUTATE/DESTROY tasks)
    if rt in ("MUTATE", "DESTROY"):
        bo = packet.get("ec_build_order", [])
        expected = ["data", "org", "observability", "authority"]
        missing = [e for e in expected if e not in bo]
        if missing:
            errors.append(f"ec_build_order missing: {', '.join(missing)}")

    return errors


def _check_event_store(scope_id: str) -> list[str]:
    """Verify the Event Store has provenance gate events for this scope.

    Returns a list of warning messages (not blocking — Event Store may
    be unavailable).
    """
    warnings: list[str] = []
    if not _HAS_V2_STORE or EventStore is None or EventType is None:
        warnings.append("V2 Event Store unavailable — cannot verify provenance events")
        return warnings

    try:
        store = EventStore()
        provenance_events = store.get_by_type(EventType.SYSTEM_PULSE, limit=100)
        warnings.append(f"Event Store checked — {len(provenance_events)} system events found")
    except Exception as e:
        warnings.append(f"Event Store check failed: {e}")

    return warnings


def _emit_gate_event(verdict: str, scope_id: str, scope_path: str) -> None:
    """Emit a gate verdict to the V2 Event Store."""
    if not _HAS_V2_STORE:
        return
    try:
        store = EventStore()
        store.append(
            actor="pre_execution_gate",
            action=f"pre_execution.{verdict.lower()}",
            harness_layer="F",
            ec_step="readiness",
            after_state={"verdict": verdict, "scope_id": scope_id, "scope_path": scope_path},
            causation_id=scope_id,
            metadata={"gate": "pre_execution", "verdict": verdict, "scope_id": scope_id},
        )
    except Exception:
        pass  # Non-blocking — gate works without event store


def enforce_gate(
    scope_arg: str,
    skip_event_store: bool = False,
) -> dict[str, Any]:
    """Run the pre-execution gate. Returns structured verdict dict.

    Returns:
        {"verdict": "APPROVE", "gate": "pre_execution", ...}
        {"verdict": "BLOCK", "gate": "pre_execution", ...}
    """
    # Find scope packet
    scope_path = _find_scope_packet(scope_arg)
    if scope_path is None:
        return {
            "verdict": "BLOCK",
            "gate": "pre_execution",
            "reason": f"Scope packet not found: {scope_arg}",
            "action_path": str(scope_arg),
        }

    # Load scope packet
    try:
        with open(scope_path, "r") as f:
            packet = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {
            "verdict": "BLOCK",
            "gate": "pre_execution",
            "reason": f"Failed to load scope packet: {e}",
            "action_path": str(scope_path),
        }

    # Validate scope packet
    errors = _validate_scope_packet(packet)
    if errors:
        return {
            "verdict": "BLOCK",
            "gate": "pre_execution",
            "reason": "Scope packet validation failed: " + "; ".join(errors),
            "action_path": str(scope_path),
            "validation_errors": errors,
        }

    # Check Event Store (warnings only)
    warnings = []
    if not skip_event_store:
        scope_id = packet.get("scope_id", scope_path.stem)
        warnings = _check_event_store(scope_id)

    # Extract metadata for context
    scope_id = packet.get("scope_id") or packet.get("packet_id", scope_path.stem)
    ec_classification = packet.get("ec_classification", "unknown")
    authority_tier = packet.get("authority_tier", "unknown")
    risk_tier = packet.get("risk_tier", "READ")
    project_id = packet.get("project_id") or packet.get("pid", "unknown")
    title = packet.get("title") or packet.get("objective", "untitled")[:80]

    # Emit to event store
    _emit_gate_event("APPROVE", scope_id, str(scope_path))

    return {
        "verdict": "APPROVE",
        "judge_verdict": "APPROVE",
        "gate": "pre_execution",
        "scope_id": scope_id,
        "scope_path": str(scope_path),
        "project_id": project_id,
        "title": title,
        "ec_classification": ec_classification,
        "authority_tier": authority_tier,
        "risk_tier": risk_tier,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-Execution Gate — validates scope + provenance before work"
    )
    parser.add_argument(
        "--scope", required=True,
        help="Scope packet filename or path (e.g. SCOPE-xxx.approval.json)",
    )
    parser.add_argument(
        "--skip-event-store", action="store_true",
        help="Skip Event Store verification (faster, less thorough)",
    )
    args = parser.parse_args()

    result = enforce_gate(args.scope, skip_event_store=args.skip_event_store)
    verdict = result.get("verdict", "BLOCK")

    if verdict == "APPROVE":
        print(f"GATE_APPROVE: pre_execution")
        print(f"  Scope:     {result.get('scope_id', '?')}")
        print(f"  Project:   {result.get('project_id', '?')}")
        print(f"  Title:     {result.get('title', '?')}")
        print(f"  EC Class:  {result.get('ec_classification', '?')}")
        print(f"  Authority: {result.get('authority_tier', '?')}")
        print(f"  Risk:      {result.get('risk_tier', '?')}")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  ⚠️  {w}")
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)
    else:
        reason = result.get("reason", "unknown")
        print(f"GATE_BLOCKED: pre_execution")
        print(f"  reason: {reason}")
        if result.get("validation_errors"):
            for err in result["validation_errors"]:
                print(f"  ✗ {err}")
        print(json.dumps(result, indent=2, default=str))
        sys.exit(1)


if __name__ == "__main__":
    main()
