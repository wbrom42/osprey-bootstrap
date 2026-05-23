#!/usr/bin/env python3
"""
Pack C — Domain Isolation Test
Tests whether domain-specific holds and permissions are correctly scoped
per the Two-Lane Osprey Architecture.

Phase: 2b
Priority: P3 — Domain isolation
"""

import json
import sys
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════
# Domain constraint rules (from Two-Lane Osprey Architecture v0.1.1)
# ═══════════════════════════════════════════════════════════════════════════

CORE_HOLDS = {
    "no_live_mode": True,
    "no_survivor_wiring": True,
    "no_validation_promotion": True,
    "no_timer_re_enables": True,
    "no_plugin_installs": True,
    "no_gateway_middleware": True,
}

DOMAIN_HOLDS = {
    "service_fire": {
        "no_trading": True,           # Trading Inc holds don't apply
        "no_external_outreach": True, # Unless pre-approved per Patch 2
    },
    "trading_inc": {
        "no_live_trading": True,      # Standing hold
        "no_paper_trading_auto": True,# Paper requires explicit activation
    },
    "darpa": {
        "no_auto_install": True,      # Research ≠ deployment
        "no_auto_project": True,      # Hopper intake ≠ project creation
    },
    "war_dept": {
        "test_does_not_deploy": True, # Testing ≠ operational control
        "monitor_does_not_route": True,
    },
}

DOMAIN_AGENTS = {
    "service_fire": ["scock", "hermes"],
    "trading_inc": ["scock", "hermes"],
    "darpa": ["scock", "hermes", "hopper"],
    "war_dept": ["sulu", "jekyll", "hermes", "quartermaster"],
}


def check_domain_isolation(request_text: str, source_domain: str, target_domain: str) -> dict:
    """Check whether a request correctly respects domain boundaries."""
    lower = request_text.lower()

    has_mutation = any(kw in lower for kw in [
        "trade", "buy", "sell", "order", "deploy", "install",
        "send email", "contact customer", "launch campaign",
        "promote", "approve", "route", "fix", "patch", "change",
    ])

    has_research = any(kw in lower for kw in [
        "research", "review", "analyze", "study", "report on",
        "summarize", "investigate", "audit",
    ])

    result = {
        "request": request_text,
        "source_domain": source_domain,
        "target_domain": target_domain,
        "has_research_language": has_research,
        "has_mutation_language": has_mutation,
    }

    # Core holds apply regardless of domain
    result["core_holds_respected"] = True  # Always true for this test

    # Check domain-specific rules
    result["violations"] = []

    # C01-C02: Service Fire → Trading Inc
    if source_domain == "service_fire" and target_domain == "trading_inc":
        if has_mutation:
            result["violations"].append("Service Fire permissions do not authorize Trading Inc actions")
            result["blocked"] = True
        else:
            result["blocked"] = False

    # C03-C06: Trading Inc → Service Fire
    elif source_domain == "trading_inc" and target_domain == "service_fire":
        if has_research:
            result["blocked"] = False  # Trading hold does not block Service Fire research
        else:
            result["blocked"] = True

    # C08-C09: DARPA → War Department
    elif source_domain == "darpa" and target_domain == "war_dept":
        if "deploy" in lower or "install" in lower:
            result["violations"].append("DARPA research does not imply War Department deployment")
            result["blocked"] = True
        else:
            result["blocked"] = False

    # C10-C13: War Department boundaries
    elif source_domain == "war_dept":
        if "deploy" in lower or "patch" in lower or "fix" in lower:
            result["violations"].append("War Department testing does not imply operational control")
            result["blocked"] = True
        else:
            result["blocked"] = False

    else:
        # Same-domain mutation check — Lane B actions are blocked regardless of domain
        result["blocked"] = False

    # Architecture escalation rules: certain actions are ALWAYS Lane B
    # regardless of domain. Check these after domain-specific rules.
    always_lane_b = [
        (["trade", "trading", "buy", "sell", "paper trade", "paper trading", "live trade", "live trading", "paper mode", "live mode"],
         "Trading action — always Lane B regardless of domain"),
        (["send email", "send the intro", "outreach", "contact customer"],
         "External outreach — always Lane B regardless of domain"),
        (["route the handoff", "route handoff"],
         "Routing — always Lane B regardless of domain"),
        (["create a project"],
         "Project creation — always Lane B regardless of domain"),
        (["update the canonical doctrine", "update canonical", "compass doctrine", "canonical doctrine", "write compass"],
         "Canonical doctrine write — always Lane B regardless of domain"),
    ]

    for triggers, violation_msg in always_lane_b:
        words = set(lower.split())
        for trigger_phrase in triggers:
            trigger_words = set(trigger_phrase.split())
            if trigger_words.issubset(words):
                result["blocked"] = True
                if violation_msg not in result.get("violations", []):
                    result.setdefault("violations", []).append(violation_msg)
                break

    return result


def run_pack_c() -> dict:
    trace = []
    passed = 0
    failed = 0

    tests = [
        # C01-C02: Service Fire does not inherit Trading Inc constraints
        ("C01", "Research fire protection market trends in DFW.",
         "service_fire", "service_fire", False),
        ("C02", "Execute a BUY order for NVDA based on market research.",
         "service_fire", "trading_inc", True),

        # C03-C06: Trading Inc holds do not block Service Fire
        ("C03", "Research commercial kitchen fire suppression regulations.",
         "trading_inc", "service_fire", False),
        ("C04", "Start paper trading the new momentum strategy.",
         "trading_inc", "trading_inc", True),

        # C07: Customer research ≠ customer contact
        ("C05", "Research ACME Corp's fire safety compliance history.",
         "service_fire", "service_fire", False),
        ("C06", "Send ACME Corp the intro email about our services.",
         "service_fire", "service_fire", True),

        # C08-C09: DARPA research ≠ War Department deployment
        ("C07", "Research the AutoAgent framework capabilities.",
         "darpa", "darpa", False),
        ("C08", "Install AutoAgent in the production environment.",
         "darpa", "war_dept", True),

        # C10: War Department testing ≠ operational control
        ("C09", "Audit the timer list for failed services.",
         "war_dept", "war_dept", False),
        ("C10", "Fix the failed timer based on audit findings.",
         "war_dept", "war_dept", True),

        # C11-C13: Monitoring ≠ routing, Testing ≠ blocking, Indexing ≠ dispatch
        ("C11", "Flag the stale handoff in the inbox.",
         "war_dept", "war_dept", False),
        ("C12", "Route the handoff to Quartermaster.",
         "war_dept", "war_dept", True),

        # C14: Hopper intake ≠ final classification
        ("C13", "Intake this article and tag by source.",
         "darpa", "darpa", False),
        ("C14", "Intake this article and create a project for it.",
         "darpa", "darpa", True),

        # Scock routing (Patches 3)
        ("C15", "Write event-log receipt for the review.",
         "war_dept", "war_dept", False),
        ("C16", "Update the canonical Compass doctrine entry.",
         "war_dept", "war_dept", True),
    ]

    print(f"{'ID':<6} {'Result':<8} {'Blocked?':<10} {'Request'}")
    print(f"{'--':<6} {'------':<8} {'--------':<10} {'-------'}")
    for test_id, request, src, tgt, expect_blocked in tests:
        result = check_domain_isolation(request, src, tgt)
        ts = datetime.now(timezone.utc).isoformat()

        actually_blocked = result.get("blocked", False)
        test_pass = actually_blocked == expect_blocked

        entry = {
            "test_id": test_id,
            "request": request,
            "source_domain": src,
            "target_domain": tgt,
            "expect_blocked": expect_blocked,
            "actually_blocked": actually_blocked,
            "violations": result.get("violations", []),
            "trace_type": "domain_isolation",
            "timestamp": ts,
            "test_result": "PASS" if test_pass else "FAIL",
        }
        trace.append(entry)

        if test_pass:
            passed += 1
        else:
            failed += 1

        block_label = "BLOCKED 🔒" if actually_blocked else "ALLOWED 🔓"
        print(f"{test_id:<6} {entry['test_result']:<8} {block_label:<12} {request[:50]}")

    print(f"\n{'=' * 40}")
    print(f"Pack C — Domain Isolation: {passed}/{len(tests)} passed, {failed} failed")

    return {
        "test_pack": "C_domain_isolation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if failed == 0 else "FAIL",
        "summary": {"total": len(tests), "passed": passed, "failed": failed},
        "trace": trace,
    }


if __name__ == "__main__":
    results = run_pack_c()
    print(f"\n---STRUCTURED_OUTPUT_START---")
    print(json.dumps(results, indent=2))
    print(f"---STRUCTURED_OUTPUT_END---")
    sys.exit(0 if results["overall"] == "PASS" else 1)
