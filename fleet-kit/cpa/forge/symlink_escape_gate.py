#!/usr/bin/env python3
"""Symlink Escape Gate — detects path escapes through symlinks in allowed_paths.

Pack F / F08 gap closure. Resolves realpath before authorizing file writes.
A write to an allowed_path that resolves to a forbidden target via symlink
is BLOCKED.

Closes: Pack F scenario F08 (gate_cascade) — symlink escape from allowed_path.

Usage:
    python3 symlink_escape_gate.py --path <target> --allowed-paths <paths.json>

Exit codes:
    0 = PATH_ALLOWED (real target is within allowed_paths)
    1 = PATH_BLOCKED (symlink escape detected or path outside allowed_paths)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def resolve_safe(target: str) -> tuple[str, list[str]]:
    """Resolve a path to its real location, tracking symlink chain.

    Returns (real_path, symlink_chain) where symlink_chain lists
    each symlink resolved along the way.
    """
    chain: list[str] = []
    p = Path(target)

    # Resolve each component, catching symlinks
    parts = p.parts
    resolved = Path(p.root) if p.is_absolute() else Path(".")
    
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            resolved = resolved.parent
            continue
        candidate = resolved / part
        try:
            if candidate.is_symlink():
                link_target = os.readlink(str(candidate))
                chain.append(f"{candidate} -> {link_target}")
        except OSError:
            pass
        resolved = candidate

    try:
        real = str(resolved.resolve(strict=False))
    except Exception:
        real = str(resolved)

    return real, chain


def is_within_allowed(target_real: str, allowed_paths: list[str]) -> bool:
    """Check if resolved target is within any allowed path."""
    target = Path(target_real).resolve()
    for allowed_raw in allowed_paths:
        allowed = Path(allowed_raw).expanduser().resolve()
        try:
            target.relative_to(allowed)
            return True
        except ValueError:
            continue
    return False


def check_path(target: str, allowed_paths: list[str]) -> dict[str, Any]:
    """Full symlink-aware path check.

    Returns a verdict dict with:
      - allowed: bool
      - real_path: resolved target path
      - symlink_chain: list of symlinks traversed
      - reason: human-readable explanation
    """
    real_path, symlink_chain = resolve_safe(target)

    if not symlink_chain:
        # No symlinks — standard path check
        allowed = is_within_allowed(real_path, allowed_paths)
        if allowed:
            return {
                "allowed": True,
                "real_path": real_path,
                "symlink_chain": [],
                "symlink_escape_detected": False,
                "reason": f"Path {real_path} is within allowed_paths",
            }
        else:
            return {
                "allowed": False,
                "real_path": real_path,
                "symlink_chain": [],
                "symlink_escape_detected": False,
                "reason": f"Path {real_path} is NOT within any allowed_path",
            }

    # Symlinks detected — check BOTH original and resolved
    # Original: does it appear in allowed_paths?
    original_allowed = is_within_allowed(target, allowed_paths)
    # Real: does it resolve inside allowed_paths?
    real_allowed = is_within_allowed(real_path, allowed_paths)

    if original_allowed and real_allowed:
        # Symlink but target stays within allowed — ALLOW
        return {
            "allowed": True,
            "real_path": real_path,
            "symlink_chain": symlink_chain,
            "symlink_escape_detected": False,
            "reason": f"Symlink detected but target {real_path} stays within allowed_paths",
        }
    elif original_allowed and not real_allowed:
        # SYMLINK ESCAPE — original in allowed but real target outside
        return {
            "allowed": False,
            "real_path": real_path,
            "symlink_chain": symlink_chain,
            "symlink_escape_detected": True,
            "reason": f"SYMLINK ESCAPE: {target} resolves to {real_path} which is outside allowed_paths. Chain: {' -> '.join(symlink_chain)}",
        }
    elif not original_allowed and real_allowed:
        # Target via symlink lands in allowed — edge case, ALLOW with warning
        return {
            "allowed": True,
            "real_path": real_path,
            "symlink_chain": symlink_chain,
            "symlink_escape_detected": False,
            "reason": f"Path resolves to {real_path} within allowed_paths (via symlink)",
        }
    else:
        return {
            "allowed": False,
            "real_path": real_path,
            "symlink_chain": symlink_chain,
            "symlink_escape_detected": False,
            "reason": f"Both original and resolved paths outside allowed_paths",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Symlink Escape Gate")
    parser.add_argument("--path", required=True, help="Target path to check")
    parser.add_argument("--allowed-paths", required=True, help="JSON file or JSON string of allowed paths")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    # Parse allowed paths
    allowed_raw = args.allowed_paths
    if os.path.isfile(allowed_raw):
        with open(allowed_raw) as f:
            allowed_paths = json.load(f)
    else:
        try:
            allowed_paths = json.loads(allowed_raw)
        except json.JSONDecodeError:
            allowed_paths = [allowed_raw]

    if not isinstance(allowed_paths, list):
        allowed_paths = [str(allowed_paths)]

    result = check_path(args.path, allowed_paths)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        verdict = "✅ ALLOWED" if result["allowed"] else "❌ BLOCKED"
        print(f"{verdict}: {result['reason']}")
        if result["symlink_chain"]:
            print(f"  Symlink chain: {' -> '.join(result['symlink_chain'])}")

    sys.exit(0 if result["allowed"] else 1)


if __name__ == "__main__":
    main()
