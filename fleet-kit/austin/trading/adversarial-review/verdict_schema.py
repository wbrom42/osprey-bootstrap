"""
D-013-001: Verdict Schema for Adversarial Review

Structured output schemas for debate transcripts, judgment records,
and all associated data types used in the thesis adversarial review pipeline.
"""
from __future__ import annotations
from typing import Any

# ── Argument Schemas ──────────────────────────────────────────────────────

ARGUMENT_FIELDS = {
    "argument": {"type": str, "required": True, "desc": "Clear statement of the argument"},
    "evidence": {"type": str, "required": True, "desc": "Specific data/evidence supporting the argument"},
    "conviction": {"type": (int, float), "required": True, "desc": "Conviction score 1-10"},
    "falsification": {"type": str, "required": True, "desc": "Criteria that would disprove this argument"},
    "time_horizon_days": {"type": int, "required": True, "desc": "Expected time horizon in days"},
}

BULL_ARGUMENT_FIELDS = {
    **ARGUMENT_FIELDS,
    "catalyst": {"type": str, "required": True, "desc": "What event/condition triggers this thesis"},
    "risk_factor": {"type": str, "required": False, "desc": "Identified risk to this argument"},
}

BEAR_ARGUMENT_FIELDS = {
    **ARGUMENT_FIELDS,
    "risk": {"type": str, "required": True, "desc": "What specific risk this poses to the thesis"},
    "mitigation": {"type": str, "required": False, "desc": "What would reduce this risk"},
}

# ── Debate Transcript Schema ──────────────────────────────────────────────

DEBATE_TRANSCRIPT_SCHEMA = {
    "debate_id": {"type": str, "required": True},
    "debated_at": {"type": str, "required": True},
    "thesis": {"type": dict, "required": True},
    "bull_arguments": {"type": list, "required": True},
    "bear_arguments": {"type": list, "required": True},
    "bull_strength": {"type": str, "required": True, "values": ["WEAK", "MODERATE", "STRONG"]},
    "bear_strength": {"type": str, "required": True, "values": ["WEAK", "MODERATE", "STRONG"]},
    "key_disagreements": {"type": list, "required": False},
    "unresolved_questions": {"type": list, "required": False},
    "debate_summary": {"type": str, "required": False},
}

# ── Verdict / JUDGE Result Schema ─────────────────────────────────────────

JUDGE_VERDICT_SCHEMA = {
    "verdict": {"type": str, "required": True, "values": ["SUPPORT_THESIS", "REJECT_THESIS", "NEUTRAL"]},
    "conviction_score": {"type": (int, float), "required": True},
    "reasoning": {"type": str, "required": True},
    "strongest_bull_argument": {"type": str, "required": True},
    "strongest_bear_argument": {"type": str, "required": True},
    "key_conflicts": {"type": list, "required": False},
    "unresolved_questions": {"type": list, "required": False},
    "recommended_action": {"type": str, "required": False, "values": ["PROCEED", "REVISE", "ESCALATE"]},
    "risk_assessment": {"type": str, "required": False, "values": ["LOW", "MEDIUM", "HIGH"]},
    "time_horizon_assessment": {"type": str, "required": False},
    "falsification_monitoring": {"type": list, "required": False},
}

# ── Conviction / Strength Helper ──────────────────────────────────────────

def calculate_strength(arguments: list[dict], label: str = "argument") -> str:
    """Derive WEAK/MODERATE/STRONG rating from argument conviction scores.

    Args:
        arguments: List of argument dicts, each with a 'conviction' key
        label: Label for logging purposes

    Returns:
        'WEAK', 'MODERATE', or 'STRONG'
    """
    if not arguments:
        return "WEAK"

    scores = [a.get("conviction", 5) for a in arguments if isinstance(a, dict)]
    if not scores:
        return "WEAK"

    avg = sum(scores) / len(scores)
    if avg >= 7.5:
        return "STRONG"
    elif avg >= 5.0:
        return "MODERATE"
    return "WEAK"


# ── Gate / Action Verdict Schema ──────────────────────────────────────────

GATE_VERDICT_SCHEMA = {
    "verdict": {"type": str, "required": True, "values": ["APPROVE", "REVISE", "ESCALATE", "BLOCK", "ABSTAIN"]},
    "gate": {"type": str, "required": True},
    "reason": {"type": str, "required": True},
    "override": {"type": bool, "required": False},
}

# ── Validation function ───────────────────────────────────────────────────

def validate_against_schema(data: dict, schema: dict) -> list[str]:
    """Validate a dict against a schema definition.

    Args:
        data: The dict to validate
        schema: Schema dict with field_name -> {type, required, values}

    Returns:
        List of validation error strings (empty = valid)
    """
    errors = []
    for field, spec in schema.items():
        if spec.get("required") and field not in data:
            errors.append(f"Missing required field: {field}")
            continue

        val = data.get(field)
        if val is None and not spec.get("required"):
            continue

        if val is not None:
            expected_type = spec["type"]
            if isinstance(expected_type, tuple):
                if not isinstance(val, expected_type):
                    errors.append(
                        f"Field '{field}': expected one of {expected_type}, got {type(val).__name__}"
                    )
            elif not isinstance(val, expected_type):
                errors.append(
                    f"Field '{field}': expected {expected_type.__name__}, got {type(val).__name__}"
                )

            values = spec.get("values")
            if values and isinstance(val, str) and val not in values:
                errors.append(f"Field '{field}': value '{val}' not in allowed values {values}")

    return errors


def validate_argument(arg: dict, schema: dict) -> list[str]:
    """Validate a single argument dict against a schema."""
    return validate_against_schema(arg, schema)


def validate_debate_transcript(transcript: dict) -> list[str]:
    """Validate a complete debate transcript."""
    errors = validate_against_schema(transcript, DEBATE_TRANSCRIPT_SCHEMA)
    # Validate individual arguments
    for side, field in [("bull", "bull_arguments"), ("bear", "bear_arguments")]:
        side_schema = BULL_ARGUMENT_FIELDS if side == "bull" else BEAR_ARGUMENT_FIELDS
        for i, arg in enumerate(transcript.get(field, [])):
            arg_errs = validate_argument(arg, side_schema)
            for e in arg_errs:
                errors.append(f"{field}[{i}]: {e}")
    return errors


def validate_judge_verdict(verdict: dict) -> list[str]:
    """Validate a judge verdict record."""
    return validate_against_schema(verdict, JUDGE_VERDICT_SCHEMA)
