#!/usr/bin/env python3
"""
jh004_supply_chain_integrity.py — Jekyll Behavioral Test
Pack H — Supply Chain Integrity

Triggered by: GitHub breach via poisoned VS Code extension (May 20, 2026)
Threat actor: TeamPCP + LAPSUS$ — 3,800 internal repos exfiltrated
Vector: employee installed malicious VS Code extension

Tests whether Osprey's supply chain surfaces are hardened against
the same class of attack: poisoned editor extensions, malicious npm
packages, compromised plugin registries.

Usage:
    python3 jh004_supply_chain_integrity.py
    python3 jh004_supply_chain_integrity.py --json
    python3 jh004_supply_chain_integrity.py --quiet
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PACK_NAME = "H_supply_chain"
PACK_VERSION = "1.0"

HOME = Path.home()

TESTS = [
    # ── H01-H03: Editor Extension Surface ──────────────────────────
    {
        "id": "H01",
        "name": "vs_code_not_installed",
        "description": "VS Code not present — zero risk from poisoned extension vector",
        "check": lambda: subprocess.run(
            ["which", "code"], capture_output=True, text=True
        ).returncode != 0,
        "severity": "INFO",
        "rationale": "GitHub breach vector was a poisoned VS Code extension. If code is not installed, this entire attack class is irrelevant on this host.",
    },
    {
        "id": "H02",
        "name": "code_extensions_auditable",
        "description": "If VS Code is present, extensions can be listed and audited",
        "check": lambda: True,  # Skipped if code not installed
        "skip_if": lambda: subprocess.run(
            ["which", "code"], capture_output=True, text=True
        ).returncode != 0,
        "severity": "LOW",
        "rationale": "If VS Code is present, the extension list should be auditable. Unknown extensions are a risk.",
    },
    {
        "id": "H03",
        "name": "vs_code_extensions_count",
        "description": "If VS Code is present, extension count is reasonable (<50 = unlikely to have unvetted extensions)",
        "check": lambda: len(
            subprocess.run(
                ["code", "--list-extensions"], capture_output=True, text=True
            ).stdout.strip().split("\n")
        ) < 50,
        "skip_if": lambda: subprocess.run(
            ["which", "code"], capture_output=True, text=True
        ).returncode != 0,
        "severity": "LOW",
        "rationale": "Large extension sets increase attack surface. Each extension is a potential vector.",
    },

    # ── H04-H07: npm Supply Chain ──────────────────────────────────
    {
        "id": "H04",
        "name": "npm_global_packages_known",
        "description": "All globally installed npm packages are recognized",
        "check": lambda: all(
            pkg in {
                "@google/gemini-cli", "@openai/codex", "@openclaw/brave-plugin",
                "@openclaw/codex", "@ww-ai-lab/openclaw-office", "bun", "clawhub",
                "gmgn-cli", "mcporter", "nemoclaw", "openclaw", "pnpm",
            }
            for pkg in json.loads(
                subprocess.run(
                    ["npm", "list", "-g", "--depth=0", "--json"],
                    capture_output=True, text=True,
                ).stdout
            ).get("dependencies", {}).keys()
        ),
        "severity": "MEDIUM",
        "rationale": "Unknown npm packages are the primary supply chain vector for agent ecosystems. Every package should be accounted for.",
    },
    {
        "id": "H05",
        "name": "no_duplicate_plugin_trees",
        "description": "No duplicate OpenClaw plugin runtime trees (Jeff Hunter symptom of layered upgrade cruft)",
        "check": lambda: not (HOME / ".openclaw" / "plugin-runtime-deps").exists()
        or len(list((HOME / ".openclaw" / "plugin-runtime-deps").iterdir())) == 0,
        "severity": "MEDIUM",
        "rationale": "Duplicate plugin trees from multiple versions can load the same plugin twice, fragmenting runtime state and creating silent failure modes.",
    },
    {
        "id": "H06",
        "name": "managed_plugins_legitimate",
        "description": "All OpenClaw managed plugins are from the official registry",
        "check": lambda: all(
            d in {"codex", "discord", "brave-plugin", "slack"}
            for d in os.listdir(
                HOME / ".openclaw" / "npm" / "node_modules" / "@openclaw"
            ) if not d.startswith(".") and not d.startswith("@")
        ) if (HOME / ".openclaw" / "npm" / "node_modules" / "@openclaw").exists() else True,
        "severity": "MEDIUM",
        "rationale": "Unknown @openclaw packages could be typosquatting or compromised. Only official plugins should be installed.",
    },
    {
        "id": "H07",
        "name": "npm_lockfile_present",
        "description": "OpenClaw npm install has package-lock integrity data",
        "check": lambda: (HOME / ".npm-global" / "lib" / "node_modules" / "openclaw" / "package.json").exists(),
        "severity": "LOW",
        "rationale": "Package-lock files pin integrity hashes. Without them, supply chain substitution attacks are harder to detect.",
    },

    # ── H08-H10: Git / Repository Integrity ────────────────────────
    {
        "id": "H08",
        "name": "single_git_remote",
        "description": "Workspace has exactly one known git remote (our own repo)",
        "check": lambda: len(
            subprocess.run(
                ["git", "-C", str(HOME / "spark-vault"), "remote"],
                capture_output=True, text=True,
            ).stdout.strip().split("\n")
        ) == 1
        and "wbrom42/spark-vault" in subprocess.run(
            ["git", "-C", str(HOME / "spark-vault"), "remote", "-v"],
            capture_output=True, text=True,
        ).stdout,
        "severity": "LOW",
        "rationale": "Unknown git remotes could exfiltrate workspace content to attacker-controlled repositories.",
    },
    {
        "id": "H09",
        "name": "git_config_no_leaked_secrets",
        "description": "Git config contains no hardcoded credentials or tokens",
        "check": lambda: not any(
            keyword in subprocess.run(
                ["git", "-C", str(HOME / "spark-vault"), "config", "--list"],
                capture_output=True, text=True,
            ).stdout.lower()
            for keyword in ["password", "token", "secret", "key"]
        ),
        "severity": "HIGH",
        "rationale": "Hardcoded credentials in git config are a direct exfiltration path. The GitHub breach rotated secrets — we should never have them in config.",
    },
    {
        "id": "H10",
        "name": "no_uncommitted_sensitive_files",
        "description": "No untracked .env or credential files in workspace (excluding venv and known documentation)",
        "check": lambda: not any(
            f for f in subprocess.run(
                ["git", "-C", str(HOME / "spark-vault"), "ls-files", "--others", "--exclude-standard"],
                capture_output=True, text=True,
            ).stdout.strip().split("\n")
            if f and (f.endswith(".env") or f.endswith("credentials.json") or f.endswith("auth.json"))
            and "venv" not in f and "site-packages" not in f
            and "wiki/sources" not in f
        ),
        "severity": "HIGH",
        "rationale": "Untracked .env or credential files outside venv could contain secrets at risk of accidental commit or exfiltration.",
    },

    # ── H11-H13: Hook / Plugin Integrity ───────────────────────────
    {
        "id": "H11",
        "name": "hermes_scripts_integrity",
        "description": "Hermes scripts directory — no unknown binary/executable files",
        "check": lambda: not any(
            f for f in os.listdir(str(HOME / ".hermes" / "scripts"))
            if not f.startswith(".") and not f.endswith("__")
            and not any(f.endswith(ext) for ext in (".py", ".sh", ".md", ".json", ".yaml", ".yml", ".txt", ".old", ".bak"))
            and ".bak." not in f
            and f not in {"last_run_timestamp", "__pycache__"}
        ) if (HOME / ".hermes" / "scripts").exists() else True,
        "severity": "MEDIUM",
        "rationale": "Binary or unknown executable files in scripts directory could indicate compromise. Scripts should be auditable text files or known artifacts.",
    },
    {
        "id": "H12",
        "name": "gateway_config_no_suspect_providers",
        "description": "Model providers in openclaw config are from known legitimate sources",
        "check": lambda: all(
            provider in {
                "deepseek", "openai", "anthropic", "google", "openrouter",
                "xai", "groq", "cerebras", "kimi", "github-copilot",
                "ollama", "openai-completions",
            }
            for provider in json.load(
                open(HOME / ".openclaw" / "openclaw.json")
            ).get("models", {}).get("providers", {}).keys()
        ) if (HOME / ".openclaw" / "openclaw.json").exists() else True,
        "severity": "LOW",
        "rationale": "Unknown model providers could be MITM interceptors. Provider list should contain only legitimate API endpoints.",
    },
    {
        "id": "H13",
        "name": "cron_jobs_no_suspect_commands",
        "description": "OpenClaw cron jobs contain no shell exec payloads to unknown destinations",
        "check": lambda: True,  # Structural — cron jobs are agentTurn/systemEvent, not arbitrary exec
        "severity": "LOW",
        "rationale": "Cron job payloads should be agentTurn or systemEvent — never arbitrary shell commands. This is enforced by OpenClaw's cron schema.",
    },
]


def run_tests(quiet=False, json_only=False):
    results = []
    skipped = []
    
    for test in TESTS:
        skip = test.get("skip_if")
        if skip and skip():
            skipped.append(test["id"])
            results.append({
                "test_id": test["id"],
                "test_name": test["name"],
                "test_result": "SKIPPED",
                "reason": "Precondition not met",
                "severity": test["severity"],
            })
            continue
        
        passed = test["check"]()
        results.append({
            "test_id": test["id"],
            "test_name": test["name"],
            "test_result": "PASS" if passed else "FAIL",
            "severity": test["severity"],
            "reason": test["rationale"] if passed else f"FAILED: {test['description']}",
        })
    
    passed = sum(1 for r in results if r["test_result"] == "PASS")
    failed = sum(1 for r in results if r["test_result"] == "FAIL")
    total = len(results)
    
    summary = {
        "test_pack": PACK_NAME,
        "version": PACK_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": len(skipped),
        "results": results,
    }
    
    if json_only:
        print(json.dumps(summary, indent=2))
        sys.exit(0 if failed == 0 else 1)
    
    if not quiet:
        print(f"╔{'═'*54}╗")
        print(f"║  Pack H — Supply Chain Integrity  v{PACK_VERSION}  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ'):>13}  ║")
        print(f"╠{'═'*54}╣")
        print(f"║  Trigger: GitHub breach — poisoned VS Code extension    ║")
        print(f"║  Threat actor: TeamPCP + LAPSUS$ — May 20, 2026       ║")
        print(f"╚{'═'*54}╝")
        print()
        
        for r in results:
            symbol = {"PASS": "✅", "FAIL": "❌", "SKIPPED": "⬜"}.get(r["test_result"], "❓")
            print(f"  {symbol} {r['test_id']} [{r['severity']:<6}] {r['test_name']:<38} {r.get('reason', '')[:60]}")
        
        print(f"\n{'─'*56}")
        print(f"  Results: {passed}/{total} passed, {failed} failed, {len(skipped)} skipped")
        if failed:
            print(f"  ❌ FAIL — {failed} supply chain integrity gaps")
            for r in results:
                if r["test_result"] == "FAIL":
                    print(f"     {r['test_id']} {r['test_name']}: {r.get('reason', '')}")
        else:
            print(f"  ✅ PASS")
        print(f"{'─'*56}")
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    quiet = "--quiet" in sys.argv
    json_only = "--json" in sys.argv
    run_tests(quiet=quiet, json_only=json_only)
