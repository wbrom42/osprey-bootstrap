#!/usr/bin/env python3
"""
Terafab → D-013 Bridge — converts Terafab watchlist stances to D-013 thesis pipeline candidates.

Feeds the trading whitelist from I-001/A-024 Terafab research output.
Each BUY-CANDIDATE becomes a HIGH confidence thesis candidate.
HOLD-MONITOR tickers with w3+ signals become MEDIUM confidence candidates.

Usage:
    python3 terafab_to_d013.py                           # JSON output of all candidates
    python3 terafab_to_d013.py --min-tier BUY_CANDIDATE   # Only BUY-CANDIDATE names
    python3 terafab_to_d013.py --format classification    # D-013 classification records
    python3 terafab_to_d013.py --whitelist                # Output whitelist JSON

Source: A024_TERAFAB_WATCHLIST_SCREEN_V1.md + terafab-watchlist.yaml
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Terafab Watchlist → D-013 Mapping ─────────────────────────────────────

# Confidence mapping: Terafab stance + evidence weight → D-013 confidence (1-10)
CONFIDENCE_MAP = {
    "BUY-CANDIDATE": {"w5": 9.0, "w4": 8.5, "w3": 8.0, "w2": 7.0},
    "HOLD-MONITOR": {"w5": 7.0, "w4": 6.5, "w3": 6.0, "w2": 5.0, "w1": 4.0},
    "SELL-AVOID-CANDIDATE": {"w5": 2.0, "w4": 2.0, "w3": 1.0, "w2": 1.0, "w1": 1.0},
}

# Thesis mapping: Terafab thesis → D-013 thesis direction
THESIS_MAP = {
    "THESIS_A": "Infrastructure Control — AI compute bottlenecks drive sustained demand",
    "THESIS_B": "Vertical Integration — Musk builds semiconductor supply chain independence",
    "THESIS_C": "Acquisition Target — Company is a potential M&A target for Terafab vertical integration",
}

# Terafab watchlist — the canonical source of truth
# (BUY-CANDIDATE names with evidence tiers)
BUY_CANDIDATES = [
    {"ticker": "VRT", "company": "Vertiv Holdings", "stance": "BUY-CANDIDATE",
     "thesis": ["THESIS_A"], "bottleneck_fit": 5, "signal_momentum": 4,
     "evidence_tier": "w3", "confidence": 8.0, "sector": "Power & Grid",
     "rationale": "$12.45B backlog, +80% YoY, power/thermal for data centers",
     "kill_conditions": ["DC buildout deceleration", "competitor thermal disruption", "order book deceleration"]},
    {"ticker": "SMCI", "company": "Super Micro Computer", "stance": "BUY-CANDIDATE",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 4,
     "evidence_tier": "w3", "confidence": 8.0, "sector": "AI Infrastructure",
     "rationale": "$10.2B revenue, +123% YoY, 6,000 racks/month, liquid cooling leader",
     "kill_conditions": ["accounting/SEC re-escalation", "component allocation shift", "major customer loss"]},
    {"ticker": "AMKR", "company": "Amkor Technology", "stance": "BUY-CANDIDATE",
     "thesis": ["THESIS_A", "THESIS_B"], "bottleneck_fit": 4, "signal_momentum": 3,
     "evidence_tier": "w3", "confidence": 8.0, "sector": "Semiconductors",
     "rationale": "Arizona advanced packaging campus $7B, tripling capacity, TSMC outsourcing CoWoS",
     "kill_conditions": ["Arizona delays/cost overruns", "TSMC reduces outsourced packaging", "customer concentration"]},
]

# HOLD-MONITOR tickers with evidence (w3+, strong bottleneck fit, or structural thesis link)
HIGH_CONVICTION_MONITORS = [
    {"ticker": "INTC", "company": "Intel Corporation", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_B"], "bottleneck_fit": 5, "signal_momentum": 4,
     "evidence_tier": "w3", "confidence": 6.0, "sector": "Semiconductors",
     "rationale": "Foundry partner for Terafab — 14A node, Apple deal, Musk Oregon visit. Disconfirmer 3 on 18A→14A pivot.",
     "upgrade_trigger": "18A→14A disconfirmer resolution, Capital Markets Day clarity"},
    {"ticker": "NVDA", "company": "NVIDIA Corporation", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 5, "signal_momentum": -1,
     "evidence_tier": "w2", "confidence": 5.0, "sector": "Semiconductors",
     "rationale": "Primary GPU supplier to all hyperscalers. Most crowded AI trade. Signal momentum neutral/negative.",
     "upgrade_trigger": "New signal momentum, crowding relief"},
    {"ticker": "PWR", "company": "Quanta Services", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 5, "signal_momentum": 0,
     "evidence_tier": "w1", "confidence": 5.0, "sector": "Power & Grid",
     "rationale": "Perfect bottleneck fit (BN_POWER + BN_DC_CONSTRUCTION, score 5). Zero ticker-level signals. Needs contract wins.",
     "upgrade_trigger": "Contract win for xAI/SpaceX/Crusoe grid interconnection work"},
    {"ticker": "FCX", "company": "Freeport-McMoRan", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 0,
     "evidence_tier": "w1", "confidence": 5.0, "sector": "Critical Minerals",
     "rationale": "Largest public copper producer. AI data center + electrification demand structural tailwind.",
     "upgrade_trigger": "Copper price breakout, AI infrastructure demand signal"},
    {"ticker": "LRCX", "company": "Lam Research", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_B"], "bottleneck_fit": 4, "signal_momentum": 1,
     "evidence_tier": "w2", "confidence": 5.0, "sector": "Semiconductors",
     "rationale": "Designated Terafab supplier per Intel partnership. No fab-scale orders yet. The Terafab canary — when orders appear, upgrades immediately.",
     "upgrade_trigger": "Fab-scale equipment order ($500M+) for Terafab"},
    {"ticker": "GEV", "company": "GE Vernova", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 1,
     "evidence_tier": "w2", "confidence": 5.0, "sector": "Power & Grid",
     "rationale": "Gas turbines, grid equipment — 90% capacity booked through 2030. AI data center power demand structural beneficiary.",
     "upgrade_trigger": "AI data center gas turbine order announcement"},
    {"ticker": "ETN", "company": "Eaton Corporation", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 1,
     "evidence_tier": "w2", "confidence": 5.0, "sector": "Power & Grid",
     "rationale": "Electrical/switchgear + Boyd Thermal acquisition ($9.5B). Data center electrical infrastructure demand.",
     "upgrade_trigger": "Boyd Thermal integration milestones, data center backlog disclosure"},
    {"ticker": "ANET", "company": "Arista Networks", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 0,
     "evidence_tier": "w1", "confidence": 5.0, "sector": "AI Infrastructure",
     "rationale": "Data center networking — AI switches, raised target to $3.25B. No DB signals yet.",
     "upgrade_trigger": "AI switch revenue disclosure, hyperscaler contract win"},
    {"ticker": "DELL", "company": "Dell Technologies", "stance": "HOLD-MONITOR",
     "thesis": ["THESIS_A"], "bottleneck_fit": 4, "signal_momentum": 1,
     "evidence_tier": "w2", "confidence": 5.0, "sector": "AI Infrastructure",
     "rationale": "AI server racks — Colossus supplier. $50B+ debt from EMC overhang.",
     "upgrade_trigger": "Debt reduction milestone, AI server revenue disclosure"},
]

ALL_CANDIDATES = BUY_CANDIDATES + HIGH_CONVICTION_MONITORS


def to_classification(candidate: dict) -> dict:
    """Convert a Terafab candidate to a D-013 classification record."""
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "ticker": candidate["ticker"],
        "source_type": "research",
        "source_subtype": "terafab_watchlist",
        "confidence": candidate["confidence"],
        "direction": "LONG",
        "horizon": "MEDIUM_TERM",
        "signal_category": "ai_infrastructure_bottleneck",
        "thesis": " | ".join(THESIS_MAP.get(t, t) for t in candidate.get("thesis", [])),
        "sector": candidate.get("sector", ""),
        "evidence_tier": candidate.get("evidence_tier", "w1"),
        "bottleneck_fit": candidate.get("bottleneck_fit", 0),
        "signal_momentum": candidate.get("signal_momentum", 0),
        "rationale": candidate.get("rationale", ""),
        "trigger_data": {
            "stance": candidate["stance"],
            "watchlist_source": "A024_TERAFAB_WATCHLIST_SCREEN_V1",
            "upgrade_trigger": candidate.get("upgrade_trigger", ""),
            "kill_conditions": candidate.get("kill_conditions", []),
        },
        "notes": f"Terafab {candidate['stance']}: {candidate.get('rationale', '')}",
        "created_at": ts,
    }


def to_whitelist_entry(candidate: dict) -> dict:
    """Convert to a trading whitelist entry."""
    return {
        "ticker": candidate["ticker"],
        "company": candidate["company"],
        "sector": candidate["sector"],
        "terafab_stance": candidate["stance"],
        "thesis": candidate.get("thesis", []),
        "confidence": candidate["confidence"],
        "evidence_tier": candidate.get("evidence_tier", "w1"),
        "bottleneck_fit": candidate.get("bottleneck_fit", 0),
        "signal_momentum": candidate.get("signal_momentum", 0),
        "direction": "LONG",
        "horizon": "MEDIUM_TERM",
        "rationale": candidate.get("rationale", ""),
        "kill_conditions": candidate.get("kill_conditions", []),
        "upgrade_trigger": candidate.get("upgrade_trigger", ""),
        "source": "A024_TERAFAB_WATCHLIST_SCREEN_V1",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Terafab → D-013 Bridge")
    parser.add_argument("--min-tier", default="ALL", choices=["BUY_CANDIDATE", "HIGH_CONVICTION", "ALL"])
    parser.add_argument("--format", default="whitelist", choices=["whitelist", "classification"])
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args()

    if args.min_tier == "BUY_CANDIDATE":
        candidates = BUY_CANDIDATES
    elif args.min_tier == "HIGH_CONVICTION":
        candidates = BUY_CANDIDATES + HIGH_CONVICTION_MONITORS
    else:
        candidates = ALL_CANDIDATES

    ts = datetime.now(timezone.utc).isoformat()

    if args.format == "classification":
        output = {
            "source": "terafab_watchlist",
            "generated_at": ts,
            "total": len(candidates),
            "classifications": [to_classification(c) for c in candidates],
        }
    else:
        output = {
            "name": "Terafab Trading Whitelist",
            "version": "1.0",
            "source": "A024_TERAFAB_WATCHLIST_SCREEN_V1",
            "generated_at": ts,
            "total_tickers": len(candidates),
            "buy_candidates": len([c for c in candidates if c["stance"] == "BUY-CANDIDATE"]),
            "hold_monitors": len([c for c in candidates if c["stance"] == "HOLD-MONITOR"]),
            "doctrine": [
                "No source, no signal. Tickers without DB-validated signals are thesis-derived only.",
                "BUY-CANDIDATE stances require evidence path + disconfirmer review + human approval.",
                "This whitelist feeds D-013 classification pipeline, not direct execution.",
                "Kill conditions must be monitored. Any kill condition triggered → downgrade.",
            ],
            "tickers": [to_whitelist_entry(c) for c in candidates],
        }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
