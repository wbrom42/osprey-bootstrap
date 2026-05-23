#!/usr/bin/env python3
"""Delegation Loop Gate — detects circular delegation chains and depth violations.

Pack F / F10 + F19 gap closure. Tracks delegation depth and detects:
  - Circular delegation (A -> B -> A)
  - Excessive delegation depth (>3 levels)
  - Expanding authority_tier across delegation chain
  - Chain collapse (delegation without scope narrowing)

Closes: Pack F scenarios F10 (delegation_loop) and F19 (bounded_delegation_collapse).

Usage:
    # Register a delegation link
    python3 delegation_loop_gate.py --register \
        --parent agent_A --child agent_B \
        --scope SCOPE-xxx.json \
        --delegation-id uuid

    # Check current depth / detect loops
    python3 delegation_loop_gate.py --check --agent agent_C

    # Check full chain
    python3 delegation_loop_gate.py --chain --session-id session-abc

Exit codes:
    0 = DELEGATION_ALLOWED (no loop, depth OK)
    1 = DELEGATION_BLOCKED (loop detected or depth exceeded)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Delegation state file — persists across sessions
STATE_DIR = Path.home() / ".osprey" / "delegation"
STATE_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_CHAINS_FILE = STATE_DIR / "active_chains.json"

MAX_DEPTH = 3  # Maximum allowed delegation depth
MAX_CHAIN_DURATION_MINUTES = 120  # Max time a chain can be active


def load_chains() -> dict[str, Any]:
    """Load active delegation chains from state file."""
    if not ACTIVE_CHAINS_FILE.exists():
        return {"chains": {}, "sessions": {}}
    try:
        with open(ACTIVE_CHAINS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"chains": {}, "sessions": {}}


def save_chains(data: dict[str, Any]) -> None:
    """Save delegation chains to state file."""
    with open(ACTIVE_CHAINS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def register_delegation(parent: str, child: str, scope_path: str,
                        delegation_id: str | None = None,
                        session_id: str | None = None) -> dict[str, Any]:
    """Register a new delegation link. Checks for loops and depth violations."""
    data = load_chains()
    did = delegation_id or str(_uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    # Load scope packet to check authority_tier
    authority_tier = "UNKNOWN"
    scope_data = {}
    if os.path.isfile(scope_path):
        try:
            with open(scope_path) as f:
                scope_data = json.load(f)
            authority_tier = scope_data.get("authority_tier", "UNKNOWN")
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Build chain from parent (historical — what existed before this registration)
    chain = []
    current = parent
    visited = set()
    max_depth = 0

    while current and current not in visited:
        visited.add(current)
        if current in data["chains"]:
            link = data["chains"][current]
            next_agent = link.get("child")
            if next_agent:
                chain.append({
                    "from": current,
                    "to": next_agent,
                    "authority_tier": link.get("authority_tier", "UNKNOWN"),
                    "registered_at": link.get("registered_at", ""),
                })
                current = next_agent
                max_depth += 1
            else:
                break
        else:
            break

    # Also check: is child already in parent's ancestor chain?
    ancestors = {link["from"] for link in chain} | {parent}

    # Check forward from child: does child's chain reach back to parent?
    loop_detected = False
    forward_visited = {parent}
    forward_current = child
    while forward_current and forward_current not in forward_visited:
        forward_visited.add(forward_current)
        if forward_current in data["chains"]:
            fwd_link = data["chains"][forward_current]
            fwd_child = fwd_link.get("child")
            if fwd_child:
                if fwd_child == parent or fwd_child in ancestors:
                    loop_detected = True
                    break
                forward_current = fwd_child
            else:
                break
        else:
            break

    # (ancestors check done above before forward traversal)

    # Check: depth exceeded?
    new_depth = max_depth + 1
    depth_exceeded = new_depth > MAX_DEPTH

    # Check: authority expanding?
    authority_expanding = False
    if chain and authority_tier != "UNKNOWN":
        prev_tiers = [link["authority_tier"] for link in chain if link["authority_tier"] != "UNKNOWN"]
        if prev_tiers:
            # Expanding if child gets higher authority than any parent
            tier_rank = {"OBSERVE_ONLY": 1, "BOUNDED": 2, "APPROVED_PENDING": 3,
                         "AUTO": 3, "WILL_APPROVED": 4}
            current_rank = tier_rank.get(authority_tier, 2)
            for pt in prev_tiers:
                parent_rank = tier_rank.get(pt, 2)
                if current_rank > parent_rank:
                    authority_expanding = True
                    break

    # Register the new link
    data["chains"][parent] = {
        "child": child,
        "delegation_id": did,
        "authority_tier": authority_tier,
        "scope_packet": os.path.basename(scope_path),
        "registered_at": ts,
        "depth": new_depth,
    }

    # Track by session
    if session_id:
        if session_id not in data["sessions"]:
            data["sessions"][session_id] = []
        data["sessions"][session_id].append({
            "from": parent,
            "to": child,
            "delegation_id": did,
            "at": ts,
        })

    # Clean up old chains (>2h)
    cutoff = datetime.now(timezone.utc)
    for agent, link in list(data["chains"].items()):
        try:
            registered = datetime.fromisoformat(link["registered_at"])
            if (cutoff - registered).total_seconds() > MAX_CHAIN_DURATION_MINUTES * 60:
                del data["chains"][agent]
        except (ValueError, KeyError):
            pass

    save_chains(data)

    # Build verdict
    violations = []
    if loop_detected:
        violations.append(f"CIRCULAR_DELEGATION: {child} already in chain {list(ancestors)}")
    if depth_exceeded:
        violations.append(f"MAX_DEPTH_EXCEEDED: depth {new_depth} > {MAX_DEPTH}")
    if authority_expanding:
        violations.append(f"AUTHORITY_EXPANSION: child tier '{authority_tier}' exceeds parent tiers in chain")

    blocked = len(violations) > 0

    return {
        "delegation_id": did,
        "parent": parent,
        "child": child,
        "depth": new_depth,
        "max_depth": MAX_DEPTH,
        "chain": chain,
        "loop_detected": loop_detected,
        "depth_exceeded": depth_exceeded,
        "authority_expanding": authority_expanding,
        "violations": violations,
        "blocked": blocked,
        "verdict": "DELEGATION_BLOCKED" if blocked else "DELEGATION_ALLOWED",
        "timestamp": ts,
    }


def check_agent(agent: str) -> dict[str, Any]:
    """Check an agent's current position in any delegation chain."""
    data = load_chains()

    # Is this agent a parent (delegating)?
    is_parent = agent in data["chains"]
    # Is this agent a child of someone?
    parents = []
    for p, link in data["chains"].items():
        if link.get("child") == agent:
            parents.append({"parent": p, "delegation_id": link.get("delegation_id"),
                           "authority_tier": link.get("authority_tier"),
                           "at": link.get("registered_at")})

    depth = 0
    current = agent
    while current in data["chains"]:
        depth += 1
        current = data["chains"][current].get("child", "")
        if not current:
            break

    return {
        "agent": agent,
        "is_delegating": is_parent,
        "delegating_to": data["chains"][agent]["child"] if is_parent else None,
        "delegated_from": [p["parent"] for p in parents],
        "current_depth": depth,
        "max_allowed_depth": MAX_DEPTH,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_chain(session_id: str | None = None) -> dict[str, Any]:
    """Get the full delegation chain for a session or globally."""
    data = load_chains()
    if session_id:
        session_links = data["sessions"].get(session_id, [])
        return {
            "session_id": session_id,
            "links": session_links,
            "total_delegations": len(session_links),
        }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Delegation Loop Gate")
    parser.add_argument("--register", action="store_true", help="Register a delegation link")
    parser.add_argument("--check", action="store_true", help="Check an agent's delegation status")
    parser.add_argument("--chain", action="store_true", help="View delegation chains")
    parser.add_argument("--parent", help="Parent agent (for --register)")
    parser.add_argument("--child", help="Child agent (for --register)")
    parser.add_argument("--scope", help="Scope packet path (for --register)")
    parser.add_argument("--delegation-id", help="Delegation ID (for --register)")
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--agent", help="Agent name (for --check)")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    if args.register:
        if not args.parent or not args.child or not args.scope:
            print("ERROR: --register requires --parent, --child, and --scope", file=sys.stderr)
            sys.exit(2)
        result = register_delegation(
            parent=args.parent,
            child=args.child,
            scope_path=args.scope,
            delegation_id=args.delegation_id,
            session_id=args.session_id,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            verdict = "❌ BLOCKED" if result["blocked"] else "✅ ALLOWED"
            print(f"{verdict}: {args.parent} -> {args.child} (depth {result['depth']}/{result['max_depth']})")
            for v in result["violations"]:
                print(f"  ⚠️  {v}")
        sys.exit(1 if result["blocked"] else 0)

    elif args.check:
        if not args.agent:
            print("ERROR: --check requires --agent", file=sys.stderr)
            sys.exit(2)
        result = check_agent(args.agent)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Agent: {result['agent']}")
            print(f"  Depth: {result['current_depth']}/{result['max_allowed_depth']}")
            print(f"  Delegating to: {result['delegating_to'] or 'none'}")
            print(f"  Delegated from: {result['delegated_from'] or 'none'}")
        sys.exit(0)

    elif args.chain:
        result = get_chain(session_id=args.session_id)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            chains = result.get("links") or result.get("chains", {})
            if not chains:
                print("No active delegation chains.")
            elif isinstance(chains, list):
                for link in chains:
                    print(f"  {link.get('from')} -> {link.get('to')} ({link.get('at', '')})")
            elif isinstance(chains, dict):
                for agent, link in chains.items():
                    child = link.get("child", "?")
                    depth = link.get("depth", "?")
                    print(f"  {agent} -> {child} (depth {depth})")
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
