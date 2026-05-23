"""
D-013-001: Debate Engine — Adversarial Review Orchestrator

Orchestrates the bull/bear debate flow and produces a structured debate
transcript that the JUDGE module evaluates.

Flow:
1. Validate thesis structure
2. Generate bull arguments (from agent prompts or sample library)
3. Generate bear arguments (from agent prompts or sample library)
4. Assemble debate transcript with key disagreements
5. Calculate debate side strengths
6. Return structured transcript ready for JUDGE evaluation

Usage:
    python3 debate_engine.py --thesis thesis.json --output debate_transcript.json
    python3 debate_engine.py --thesis thesis.json --bull bull_args.json --bear bear_args.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Use importlib to load sibling modules (D-013 directory has hyphen, can't use dot-imports)
import importlib.util as _ilu

_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent.parent.parent.parent  # spark-vault
sys.path.insert(0, str(_PROJECT_ROOT))

# Load core adversarial_review module
_adv_spec = _ilu.spec_from_file_location(
    "adversarial_review",
    str(_PROJECT_ROOT / "projects" / "D-013" / "build" / "adversarial_review.py")
)
_adv = _ilu.module_from_spec(_adv_spec)
_adv_spec.loader.exec_module(_adv)
validate_thesis = _adv.validate_thesis
assemble_debate = _adv.assemble_debate
validate_debate = _adv.validate_debate

# Load verdict_schema
_vs_spec = _ilu.spec_from_file_location(
    "verdict_schema",
    str(_HERE / "verdict_schema.py")
)
_vs = _ilu.module_from_spec(_vs_spec)
_vs_spec.loader.exec_module(_vs)
DEBATE_TRANSCRIPT_SCHEMA = _vs.DEBATE_TRANSCRIPT_SCHEMA
BULL_ARGUMENT_FIELDS = _vs.BULL_ARGUMENT_FIELDS
BEAR_ARGUMENT_FIELDS = _vs.BEAR_ARGUMENT_FIELDS
calculate_strength = _vs.calculate_strength
validate_debate_transcript = _vs.validate_debate_transcript

# Load agent_prompts
_ap_spec = _ilu.spec_from_file_location(
    "agent_prompts",
    str(_HERE / "agent_prompts.py")
)
_ap = _ilu.module_from_spec(_ap_spec)
_ap_spec.loader.exec_module(_ap)
BULL_AGENT_SYSTEM_PROMPT = _ap.BULL_AGENT_SYSTEM_PROMPT
BEAR_AGENT_SYSTEM_PROMPT = _ap.BEAR_AGENT_SYSTEM_PROMPT
SAMPLE_BULL_ARGS_TSLA = _ap.SAMPLE_BULL_ARGS_TSLA
SAMPLE_BEAR_ARGS_TSLA = _ap.SAMPLE_BEAR_ARGS_TSLA


# ── Thesis Argument Generators ───────────────────────────────────────────

# Pre-built argument library indexed by ticker for common names
_TICKER_ARGUMENTS: dict[str, tuple[list[dict], list[dict]]] = {
    "TSLA": (SAMPLE_BULL_ARGS_TSLA, SAMPLE_BEAR_ARGS_TSLA),
}


def get_bull_prompt(thesis: dict) -> str:
    """Build a bull agent prompt from a thesis.

    Args:
        thesis: Structured thesis dict

    Returns:
        Full prompt string for the bull agent
    """
    direction = thesis.get("direction", "LONG")
    ticker = thesis.get("ticker", "UNKNOWN")
    conviction = thesis.get("conviction", "N/A")
    horizon = thesis.get("time_horizon", "N/A")
    reasoning = thesis.get("reasoning", "No reasoning provided")
    catalysts = ", ".join(thesis.get("catalysts", [])) or "None specified"
    falsification = ", ".join(thesis.get("falsification_criteria", [])) or "None specified"

    return f"""{BULL_AGENT_SYSTEM_PROMPT}

## Thesis for Review

- **Ticker:** {ticker}
- **Direction:** {direction}
- **Initial Conviction:** {conviction}/10
- **Time Horizon:** {horizon}
- **Reasoning:** {reasoning}
- **Identified Catalysts:** {catalysts}
- **Falsification Criteria:** {falsification}

Build your case FOR this thesis. Provide 3-6 structured arguments."""


def get_bear_prompt(thesis: dict) -> str:
    """Build a bear agent prompt from a thesis.

    Args:
        thesis: Structured thesis dict

    Returns:
        Full prompt string for the bear agent
    """
    direction = thesis.get("direction", "LONG")
    ticker = thesis.get("ticker", "UNKNOWN")
    conviction = thesis.get("conviction", "N/A")
    horizon = thesis.get("time_horizon", "N/A")
    reasoning = thesis.get("reasoning", "No reasoning provided")
    catalysts = ", ".join(thesis.get("catalysts", [])) or "None specified"
    falsification = ", ".join(thesis.get("falsification_criteria", [])) or "None specified"

    return f"""{BEAR_AGENT_SYSTEM_PROMPT}

## Thesis for Review

- **Ticker:** {ticker}
- **Direction:** {direction}
- **Initial Conviction:** {conviction}/10
- **Time Horizon:** {horizon}
- **Reasoning:** {reasoning}
- **Identified Catalysts:** {catalysts}
- **Falsification Criteria:** {falsification}

Challenge this thesis. Find every genuine weakness. Provide 3-6 structured arguments."""


def get_judge_prompt(thesis: dict, transcript: dict) -> str:
    """Build a judge prompt from a thesis and debate transcript.

    Args:
        thesis: Structured thesis dict
        transcript: Debate transcript with bull/bear arguments

    Returns:
        Full prompt string for the judge agent
    """
    direction = thesis.get("direction", "LONG")
    ticker = thesis.get("ticker", "UNKNOWN")
    bull_args = transcript.get("bull_arguments", [])
    bear_args = transcript.get("bear_arguments", [])

    bull_text = "\n".join(
        f"{i+1}. [{a.get('conviction', '?')}/10] {a.get('argument', '')} "
        f"— Evidence: {a.get('evidence', '')}"
        for i, a in enumerate(bull_args)
    )
    bear_text = "\n".join(
        f"{i+1}. [{a.get('conviction', '?')}/10] {a.get('argument', '')} "
        f"— Evidence: {a.get('evidence', '')}"
        for i, a in enumerate(bear_args)
    )

    return f"""{JUDGE_AGENT_SYSTEM_PROMPT}

## Thesis Under Review

- **Ticker:** {ticker}
- **Direction:** {direction}

### Bull Arguments ({len(bull_args)})
{bull_text}

### Bear Arguments ({len(bear_args)})
{bear_text}

Evaluate both sides fairly. Produce a structured verdict."""


def generate_arguments(ticker: str, thesis: dict) -> tuple[list[dict], list[dict]]:
    """Generate bull and bear arguments for a ticker.

    Uses pre-built argument library where available. In production, the
    calling agent would use delegate_task to run LLM-based generation.

    Args:
        ticker: Stock ticker symbol
        thesis: Thesis dict for context

    Returns:
        (bull_arguments, bear_arguments) tuple
    """
    ticker_key = ticker.upper()
    if ticker_key in _TICKER_ARGUMENTS:
        bull_args, bear_args = _TICKER_ARGUMENTS[ticker_key]
        return bull_args, bear_args

    # Generic fallback — score-scaled arguments based on thesis conviction
    direction = thesis.get("direction", "LONG")
    conviction = thesis.get("conviction", 5)
    # Scale bull/bear conviction so high-conviction thesis gets stronger bull args
    bull_conv = max(5, min(9, conviction))
    bear_conv = max(3, min(7, 10 - bull_conv + 2))

    bull_args = [
        {
            "argument": f"The {direction} thesis aligns with recent positive momentum",
            "evidence": f"Recent price action and volume support {direction} direction",
            "conviction": bull_conv,
            "catalyst": "Next earnings or catalyst event",
            "falsification": "Price action reverses significantly",
            "time_horizon_days": 30,
            "risk_factor": "Market-wide reversal",
        },
        {
            "argument": f"Fundamental analysis supports {direction} position",
            "evidence": "Valuation and earnings metrics are supportive",
            "conviction": max(5, bull_conv - 1),
            "catalyst": "Upcoming financial reports",
            "falsification": "Fundamental deterioration",
            "time_horizon_days": 60,
            "risk_factor": "Sector rotation",
        },
    ]

    bear_args = [
        {
            "argument": f"Risk/reward is unfavorable at current levels for {direction}",
            "evidence": "Current price already prices in expected catalysts",
            "conviction": bear_conv,
            "risk": f"Entering {direction} now could lead to poor timing",
            "falsification": "Significant new catalyst emerges",
            "time_horizon_days": 30,
            "mitigation": "Wait for pullback or better entry point",
        },
        {
            "argument": "Broader market conditions add uncertainty",
            "evidence": "Macroeconomic indicators show mixed signals",
            "conviction": max(3, bear_conv - 1),
            "risk": "Systematic risk could override thesis-specific factors",
            "falsification": "Market conditions clearly improve",
            "time_horizon_days": 60,
            "mitigation": "Hedge with broader market position",
        },
    ]

    return bull_args, bear_args


# ── Full Debate Run ──────────────────────────────────────────────────────

def run_debate(
    thesis: dict,
    bull_args: list[dict] | None = None,
    bear_args: list[dict] | None = None,
) -> dict:
    """Run a full adversarial debate on a thesis.

    Orchestrates: validate thesis → generate/pass arguments → assemble
    debate → calculate strengths → return transcript ready for JUDGE.

    Args:
        thesis: Structured thesis dict
        bull_args: Pre-supplied bull arguments (optional — auto-generated if None)
        bear_args: Pre-supplied bear arguments (optional — auto-generated if None)

    Returns:
        Structured debate transcript dict, ready for JUDGE

    Raises:
        ValueError: If thesis validation fails
    """
    # Validate thesis
    thesis_errors = validate_thesis(thesis)
    if thesis_errors:
        raise ValueError(f"Thesis validation failed: {', '.join(thesis_errors)}")

    # Generate or use supplied arguments
    ticker = thesis.get("ticker", "UNKNOWN")
    if bull_args is None or bear_args is None:
        gen_bull, gen_bear = generate_arguments(ticker, thesis)
        bull_args = bull_args or gen_bull
        bear_args = bear_args or gen_bear

    # Calculate debate side strengths from conviction scores
    bull_strength = calculate_strength(bull_args, "bull")
    bear_strength = calculate_strength(bear_args, "bear")

    # Assemble full debate transcript using the core assemble_debate function
    transcript = assemble_debate(
        thesis=thesis,
        bull_args=bull_args,
        bear_args=bear_args,
        bull_strength=bull_strength,
        bear_strength=bear_strength,
    )

    # Validate the assembled transcript
    debate_errors = validate_debate(transcript)
    schema_errors = validate_debate_transcript(transcript)
    all_errors = debate_errors + schema_errors
    if all_errors:
        raise ValueError(f"Debate assembly failed validation: {'; '.join(all_errors)}")

    # Run the JUDGE evaluate_action to check if debate passes gate
    _add_gate_status(transcript)

    return transcript


def _add_gate_status(transcript: dict) -> dict:
    """Add JUDGE gate evaluation status to the transcript.

    Uses the osprey JUDGE module to check if this debate would pass the
    adversarial review gate. Non-blocking — informational only.
    """
    try:
        _judge_spec = _ilu.spec_from_file_location(
            "judge",
            str(_PROJECT_ROOT / "osprey" / "judge" / "judge.py")
        )
        _judge = _ilu.module_from_spec(_judge_spec)
        _judge_spec.loader.exec_module(_judge)
        evaluate_action = _judge.evaluate_action

        action_doc = {
            "action_type": "trading_thesis",
            "judge_verdict": "APPROVE",
            "debate_transcript": transcript,
        }
        result = evaluate_action(action_doc)
        transcript["judge_gate_check"] = {
            "verdict": result.get("verdict"),
            "reason": result.get("reason"),
            "gate": result.get("gate"),
        }
    except ImportError:
        transcript["judge_gate_check"] = {
            "verdict": "UNKNOWN",
            "reason": "JUDGE module not available for gate check",
        }
    except Exception as e:
        transcript["judge_gate_check"] = {
            "verdict": "ERROR",
            "reason": f"Gate check failed: {e}",
        }

    return transcript


# ── CLI ──────────────────────────────────────────────────────────────────

def _load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="D-013 Adversarial Review — Debate Engine")
    parser.add_argument("--thesis", required=True, help="Thesis JSON file path")
    parser.add_argument("--bull", help="Bull arguments JSON file path (optional)")
    parser.add_argument("--bear", help="Bear arguments JSON file path (optional)")
    parser.add_argument("--output", default="debate_transcript.json", help="Output path (default: debate_transcript.json)")
    parser.add_argument("--prompts", action="store_true", help="Only print agent prompts, don't debate")
    parser.add_argument("--list-tickers", action="store_true", help="List available tickers in argument library")
    args = parser.parse_args()

    if args.list_tickers:
        print("Available tickers with pre-built arguments:")
        for ticker in sorted(_TICKER_ARGUMENTS.keys()):
            bull, bear = _TICKER_ARGUMENTS[ticker]
            print(f"  {ticker}: {len(bull)} bull args, {len(bear)} bear args")
        sys.exit(0)

    thesis = _load_json(args.thesis)

    if args.prompts:
        print("=" * 60)
        print("BULL AGENT PROMPT")
        print("=" * 60)
        print(get_bull_prompt(thesis))
        print()
        print("=" * 60)
        print("BEAR AGENT PROMPT")
        print("=" * 60)
        print(get_bear_prompt(thesis))
        sys.exit(0)

    # Load supplied arguments if provided
    bull_args = _load_json(args.bull) if args.bull else None
    bear_args = _load_json(args.bear) if args.bear else None

    # Run the debate
    try:
        transcript = run_debate(thesis, bull_args, bear_args)
    except ValueError as e:
        print(f"❌ Debate failed: {e}")
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(transcript, f, indent=2, default=str)

    print(f"✅ Debate complete: {output_path}")
    print(f"   Bull: {len(transcript['bull_arguments'])} arguments ({transcript['bull_strength']})")
    print(f"   Bear: {len(transcript['bear_arguments'])} arguments ({transcript['bear_strength']})")
    print(f"   Disagreements: {len(transcript.get('key_disagreements', []))}")
    gate_check = transcript.get("judge_gate_check", {})
    print(f"   JUDGE gate: {gate_check.get('verdict', 'N/A')} — {gate_check.get('reason', '')}")


if __name__ == "__main__":
    # Import JUDGE agent prompt lazily — may not be needed at CLI
    try:
        JUDGE_AGENT_SYSTEM_PROMPT = _ap.JUDGE_AGENT_SYSTEM_PROMPT
    except Exception:
        JUDGE_AGENT_SYSTEM_PROMPT = "JUDGE prompt not available"
    main()
