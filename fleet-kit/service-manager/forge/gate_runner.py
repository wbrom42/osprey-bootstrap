#!/usr/bin/env python3
"""Gate Runner — aggregates all enforcement gates into a single pre-flight check.

Called by pre_execution_gate.py before any delegation or scope packet execution.
Runs: delegation loop check, scope creep audit, symlink escape check (if paths
specified). Returns structured gate_results.

Usage:
    python3 gate_runner.py --packet-id SCOPE-xxx --parent-agent hermes --child-agent spock
    python3 gate_runner.py --packet-id SCOPE-xxx --check-paths /tmp/output.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SPARK_VAULT = Path.home() / "spark-vault"
ENFORCEMENT_DIR = SPARK_VAULT / "osprey" / "enforcement"

def run_gates(packet_id: str, parent_agent: str = "", child_agent: str = "",
              scope_path: str = "", check_paths: list[str] | None = None,
              allowed_paths: list[str] | None = None) -> dict:
    """Run all applicable enforcement gates and return aggregated results."""
    results = {
        "packet_id": packet_id,
        "gates_run": [],
        "all_passed": True,
        "violations": [],
        "gate_results": {},
    }

    # 1. Delegation Loop Gate
    if parent_agent and child_agent:
        import subprocess as _sp
        scope_arg = scope_path or str(SPARK_VAULT / "handoffs" / "inbox" / "real" /
                                       f"SCOPE-{packet_id}.approval.json")
        r = _sp.run([
            sys.executable, str(ENFORCEMENT_DIR / "delegation_loop_gate.py"),
            "--register", "--parent", parent_agent, "--child", child_agent,
            "--scope", scope_arg, "--json",
        ], capture_output=True, text=True, timeout=10)
        results["gates_run"].append("delegation_loop")
        try:
            d = json.loads(r.stdout)
            results["gate_results"]["delegation_loop"] = d
            if d.get("blocked"):
                results["all_passed"] = False
                results["violations"].extend(d.get("violations", []))
        except json.JSONDecodeError:
            results["gate_results"]["delegation_loop"] = {"error": r.stderr or r.stdout}

    # 2. Scope Creep Gate — audit the packet
    if packet_id:
        import subprocess as _sp2
        r = _sp2.run([
            sys.executable, str(ENFORCEMENT_DIR / "scope_creep_gate.py"),
            "--audit", "--packet-id", packet_id, "--json",
        ], capture_output=True, text=True, timeout=10)
        results["gates_run"].append("scope_creep")
        try:
            d = json.loads(r.stdout)
            results["gate_results"]["scope_creep"] = d
            if d.get("creep_detected"):
                results["all_passed"] = False
                for v in d.get("violations", []):
                    results["violations"].append(f"scope_creep: {v['violation']}")
        except json.JSONDecodeError:
            results["gate_results"]["scope_creep"] = {"error": r.stderr or r.stdout}

    # 3. Symlink Escape Gate — check specific paths
    if check_paths and allowed_paths:
        import subprocess as _sp3
        allowed_json = json.dumps(allowed_paths)
        for path in check_paths:
            r = _sp3.run([
                sys.executable, str(ENFORCEMENT_DIR / "symlink_escape_gate.py"),
                "--path", path, "--allowed-paths", allowed_json, "--json",
            ], capture_output=True, text=True, timeout=10)
            results["gates_run"].append(f"symlink_escape:{path}")
            try:
                d = json.loads(r.stdout)
                key = f"symlink_escape:{path}"
                results["gate_results"][key] = d
                if not d.get("allowed"):
                    results["all_passed"] = False
                    results["violations"].append(f"symlink_escape: {d.get('reason')}")
            except json.JSONDecodeError:
                results["gate_results"][f"symlink_escape:{path}"] = {"error": r.stderr or r.stdout}

    return results


def main():
    parser = argparse.ArgumentParser(description="Gate Runner — aggregated enforcement checks")
    parser.add_argument("--packet-id", required=True, help="Scope packet ID")
    parser.add_argument("--parent-agent", default="", help="Parent (delegating) agent")
    parser.add_argument("--child-agent", default="", help="Child (receiving) agent")
    parser.add_argument("--scope-path", default="", help="Path to scope packet file")
    parser.add_argument("--check-paths", default="", help="JSON array of paths to check for symlink escapes")
    parser.add_argument("--allowed-paths", default="", help="JSON array of allowed paths")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    check_paths = None
    allowed_paths = None
    if args.check_paths:
        check_paths = json.loads(args.check_paths)
    if args.allowed_paths:
        allowed_paths = json.loads(args.allowed_paths)

    results = run_gates(
        packet_id=args.packet_id,
        parent_agent=args.parent_agent,
        child_agent=args.child_agent,
        scope_path=args.scope_path,
        check_paths=check_paths,
        allowed_paths=allowed_paths,
    )

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        verdict = "✅ ALL GATES PASSED" if results["all_passed"] else "❌ GATE VIOLATIONS DETECTED"
        print(f"{verdict} ({len(results['gates_run'])} gates run)")
        for v in results["violations"]:
            print(f"  ⚠️  {v}")

    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
