#!/usr/bin/env python3
"""
JH-005 — Startup Context Integrity Check

Jekyll assertion: STARTUP_CONTEXT.md must exist, be readable, contain valid
YAML frontmatter, and all doctrine file pointers must resolve to real files.

If STARTUP_CONTEXT.md is missing or its pointers are broken, agents wake up
blind and may load stale doctrine without knowing it.

DETECT_REPORT_ONLY. Lane A. Never mutates.

Exit codes:
  0 = PASS (STARTUP_CONTEXT.md valid, all pointers resolve)
  1 = FAIL (missing, unreadable, bad YAML, or broken pointers)
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SPARK_VAULT = Path.home() / "spark-vault"
STARTUP_CONTEXT = SPARK_VAULT / "STARTUP_CONTEXT.md"
STARTUP_CONTEXT_HERMES = SPARK_VAULT / "STARTUP_CONTEXT-HERMES.md"

# Files that are checked by name but might be in non-standard locations
# (YAML frontmatter fields that point to file paths)
DOCTRINE_FIELDS = [
    "current_doctrine_file",
    "current_heartbeat_file",
    "current_memory_file",
    "current_soul_file",
    "current_identity_file",
    "current_user_file",
    "current_operating_manual",
    "current_projects_index",
    "current_constitution",
    "current_agents_file",
    "local_machine_truth_file",
    "access_registry_entry",
    "event_log_path",
    "supersession_registry",
]


def extract_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter between ```yaml ... ``` fences."""
    match = re.search(r'```yaml\n(.*?)\n```', text, re.DOTALL)
    if not match:
        return {}
    
    raw = match.group(1)
    result = {}
    for line in raw.split('\n'):
        line = line.strip()
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = value
    return result


def extract_hermes_yaml(text: str) -> dict:
    """Extract YAML frontmatter from Hermes-style STARTUP_CONTEXT (no yaml fence, just raw)."""
    # Hermes version has YAML between ```yaml fences too — same format
    return extract_yaml_frontmatter(text)


def clean_path(raw: str) -> str:
    """Strip comments, parenthetical notes, and resolve compound pointers."""
    # Strip parenthetical comments like "(shared with Spock)"
    raw = re.sub(r'\s*\(.*?\)\s*', '', raw).strip()
    # Handle compound pointers like "HEARTBEAT.md → projects-office/governance/..."
    if " → " in raw:
        raw = raw.split(" → ")[0].strip()
    # Strip trailing comments after #
    if " # " in raw:
        raw = raw.split(" # ")[0].strip()
    return raw


def resolve_path(field_name: str, raw_value: str) -> Path:
    """Resolve a doctrine pointer to an absolute path."""
    raw_value = clean_path(raw_value)
    if not raw_value:
        return SPARK_VAULT  # fallback, won't pass check

    # Handle ~/
    if raw_value.startswith("~/"):
        return Path.home() / raw_value[2:]

    # Handle paths starting with .hermes/ (relative to HOME, not spark-vault)
    if raw_value.startswith(".hermes/"):
        return Path.home() / raw_value

    # Handle paths that are relative to spark-vault
    p = raw_value.strip()
    candidate = SPARK_VAULT / p
    if candidate.exists() or not p.startswith("/"):
        return candidate

    return Path(p)


def check_file(path: Path, label: str) -> tuple[bool, str]:
    """Check if a file exists and is readable. Returns (ok, message)."""
    if not path.exists():
        return False, f"MISSING: {path}"
    if not path.is_file():
        return False, f"NOT_A_FILE: {path}"
    if not path.read_text(encoding='utf-8', errors='replace')[:1]:  # readable check
        return False, f"UNREADABLE: {path}"
    return True, f"OK: {path}"


def check_startup_context(sc_path: Path, label: str) -> dict:
    """Check one STARTUP_CONTEXT file. Returns result dict."""
    errors = []
    warnings = []

    # Check file exists and is readable
    if not sc_path.exists():
        return {
            "file": str(sc_path),
            "agent": label,
            "result": "FAIL",
            "errors": [f"MISSING: {sc_path}"],
            "warnings": [],
            "status": "MISSING",
        }

    if not sc_path.is_file():
        return {
            "file": str(sc_path),
            "agent": label,
            "result": "FAIL",
            "errors": [f"NOT_A_FILE: {sc_path}"],
            "warnings": [],
            "status": "NOT_A_FILE",
        }

    try:
        text = sc_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "file": str(sc_path),
            "agent": label,
            "result": "FAIL",
            "errors": [f"UNREADABLE: {e}"],
            "warnings": [],
            "status": "UNREADABLE",
        }

    # Extract YAML frontmatter
    yaml = extract_yaml_frontmatter(text)
    if not yaml:
        return {
            "file": str(sc_path),
            "agent": label,
            "result": "FAIL",
            "errors": ["No YAML frontmatter found (expected ```yaml ... ``` block)"],
            "warnings": [],
            "status": "NO_YAML",
        }

    # Check status field
    status = yaml.get("status", "?").lower()
    if status != "current":
        warnings.append(f"status is '{status}', not CURRENT")

    # Check stale_after and last_reviewed
    if "stale_after" not in yaml:
        warnings.append("missing stale_after field")
    if "last_reviewed" not in yaml:
        warnings.append("missing last_reviewed field")

    # Check all doctrine file pointers
    for field in DOCTRINE_FIELDS:
        if field not in yaml:
            continue
        raw_value = yaml[field]
        if not raw_value:
            continue

        path = resolve_path(field, raw_value)
        ok, msg = check_file(path, f"{sc_path.name} → {field}")
        if not ok:
            errors.append(f"{field}: {msg} (raw: {raw_value})")

    # Check known supersessions resolve
    known_supersessions = yaml.get("known_supersessions", "")
    # This is a list entry, not a file path — skip resolution

    result = "PASS" if not errors else "FAIL"
    if not errors and warnings:
        result = "PASS-WITH-WARNINGS"

    return {
        "file": str(sc_path),
        "agent": label,
        "result": result,
        "errors": errors,
        "warnings": warnings,
        "status": yaml.get("status", "?"),
        "last_reviewed": yaml.get("last_reviewed", "?"),
        "stale_after": yaml.get("stale_after", "?"),
    }


def main() -> int:
    results = []

    # Check Spock's STARTUP_CONTEXT
    spock_result = check_startup_context(STARTUP_CONTEXT, "Spock")
    results.append(spock_result)

    # Check Hermes's STARTUP_CONTEXT
    hermes_result = check_startup_context(STARTUP_CONTEXT_HERMES, "Hermes")
    results.append(hermes_result)

    # Summarize
    failures = [r for r in results if r["result"] == "FAIL"]
    warnings_list = [r for r in results if r["result"] == "PASS-WITH-WARNINGS"]
    passes = [r for r in results if r["result"] == "PASS"]

    print(f"JH-005: Startup Context Integrity — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}")
    print(f"  {'─'*50}")

    for r in results:
        symbol = {"PASS": "✅", "PASS-WITH-WARNINGS": "⚠️", "FAIL": "❌"}.get(r["result"], "?")
        print(f"  {symbol} {r['agent']}: {r['file']} — {r['result']}")
        if r["errors"]:
            for e in r["errors"]:
                print(f"     ✗ {e}")
        if r["warnings"]:
            for w in r["warnings"]:
                print(f"     ⚠ {w}")

    print(f"\n  Results: {len(passes)} pass, {len(warnings_list)} warnings, {len(failures)} fail")

    if failures:
        print(f"\n  🔧 Fix: Update STARTUP_CONTEXT.md doctrine pointers.")
        print(f"     Verify all referenced files exist at the paths listed in YAML frontmatter.")
        return 1

    if warnings_list:
        print(f"\n  ⚠ Warnings present but no hard failures.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
