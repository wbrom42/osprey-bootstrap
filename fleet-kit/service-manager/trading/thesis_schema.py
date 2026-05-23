"""
D-013-005: Thesis Schema — Data Models for the Thesis Pipeline

Data models for classification, thesis documents, and all intermediate
pipeline stages. All models are plain dicts with validation functions.
"""
from __future__ import annotations

from typing import Any, Optional

# ── Direction Constants ──────────────────────────────────────────────────

VALID_DIRECTIONS = ["LONG", "SHORT", "NEUTRAL"]
VALID_HORIZONS = ["INTRADAY", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"]
VALID_VERDICTS = ["SUPPORT_THESIS", "REJECT_THESIS", "NEUTRAL"]
VALID_RISK_TIERS = ["LOW", "MEDIUM", "HIGH"]
VALID_SOURCES = ["screener", "signal", "research", "insider", "congress", "macro", "manual"]

# ── Classification Models ───────────────────────────────────────────────-

def create_classification(
    ticker: str,
    source_type: str = "screener",
    signal_category: str = "",
    confidence: float = 5.0,
    trigger_data: dict | None = None,
    enrich_data: dict | None = None,
    notes: str = "",
) -> dict:
    """Create a classification record — the output of the CLASSIFY step.

    A classification is created when a screener/signal output generates
    enough interest to warrant a research question and thesis.

    Args:
        ticker: Stock ticker symbol
        source_type: Source that triggered the classification (screener, signal, etc.)
        signal_category: Category of signal (momentum, value, insider flow, etc.)
        confidence: Initial confidence score 1-10
        trigger_data: Data from the triggering source
        enrich_data: Enrichment data from cache
        notes: Human/researcher notes

    Returns:
        Classification dict
    """
    return {
        "ticker": ticker.upper(),
        "source_type": source_type,
        "signal_category": signal_category,
        "confidence": float(confidence),
        "trigger_data": trigger_data or {},
        "enrich_data": enrich_data or {},
        "notes": notes,
        "classified_at": _now_iso(),
    }


# ── Thesis Models ───────────────────────────────────────────────────────

def create_thesis(
    ticker: str,
    direction: str = "LONG",
    conviction: float = 5.0,
    time_horizon: str = "MEDIUM_TERM",
    reasoning: str = "",
    catalysts: list[str] | None = None,
    falsification_criteria: list[str] | None = None,
    entry_price: float | None = None,
    target_price: float | None = None,
    source: str = "manual",
    enrich_data: dict | None = None,
) -> dict:
    """Create a structured thesis document.

    Args:
        ticker: Stock ticker symbol
        direction: LONG / SHORT / NEUTRAL
        conviction: Conviction score 1-10
        time_horizon: INTRADAY / SHORT_TERM / MEDIUM_TERM / LONG_TERM
        reasoning: Core reasoning for the thesis
        catalysts: Events that could trigger thesis confirmation
        falsification_criteria: Conditions that would disprove the thesis
        entry_price: Target entry price
        target_price: Target exit price
        source: Source of the thesis (screener, research, etc.)
        enrich_data: Enrichment data from cache

    Returns:
        Thesis dict
    """
    return {
        "ticker": ticker.upper(),
        "direction": direction.upper(),
        "conviction": float(conviction),
        "time_horizon": time_horizon.upper(),
        "reasoning": reasoning,
        "catalysts": catalysts or [],
        "falsification_criteria": falsification_criteria or [],
        "entry_price": entry_price,
        "target_price": target_price,
        "source": source,
        "enrich_data": enrich_data or {},
        "thesis_id": _new_id("ths"),
        "created_at": _now_iso(),
        "status": "DRAFT",
    }


# ── Pipeline Stage Models ───────────────────────────────────────────────

def mark_debated(thesis: dict, debate_transcript: dict) -> dict:
    """Mark a thesis as having completed adversarial review."""
    thesis = dict(thesis)
    thesis["status"] = "DEBATED"
    thesis["debate_transcript"] = debate_transcript
    thesis["debated_at"] = _now_iso()
    return thesis


def mark_judged(thesis: dict, judge_verdict: dict) -> dict:
    """Mark a thesis as having been judged after debate."""
    thesis = dict(thesis)
    thesis["status"] = "JUDGED"
    thesis["judge_verdict"] = judge_verdict
    thesis["judged_at"] = _now_iso()
    return thesis


def mark_sized(thesis: dict, size_decision: dict) -> dict:
    """Mark a thesis as having been sized for position."""
    thesis = dict(thesis)
    thesis["status"] = "SIZED"
    thesis["size_decision"] = size_decision
    thesis["sized_at"] = _now_iso()
    return thesis


def mark_pending_act(thesis: dict, act_recommendation: dict) -> dict:
    """Mark a thesis as pending action."""
    thesis = dict(thesis)
    thesis["status"] = "PENDING_ACT"
    thesis["act_recommendation"] = act_recommendation
    thesis["acted_at"] = _now_iso()
    return thesis


def mark_paper(thesis: dict, paper_result: dict | None) -> dict:
    """Mark a thesis as paper-tracked (or not promoted)."""
    thesis = dict(thesis)
    thesis["paper_result"] = paper_result or {"verdict": "NOT_PROMOTED"}
    thesis["paper_at"] = _now_iso()
    return thesis


# ── Validation ──────────────────────────────────────────────────────────

def validate_classification(classification: dict) -> list[str]:
    """Validate a classification record. Returns list of errors."""
    errors = []
    if "ticker" not in classification:
        errors.append("Missing ticker")
    if "source_type" not in classification:
        errors.append("Missing source_type")
    confidence = classification.get("confidence", 0)
    if not isinstance(confidence, (int, float)) or confidence < 1 or confidence > 10:
        errors.append(f"confidence must be 1-10, got {confidence}")
    return errors


def validate_thesis(thesis: dict) -> list[str]:
    """Validate a thesis document. Returns list of errors."""
    errors = []
    required = ["ticker", "direction", "conviction", "time_horizon", "reasoning"]
    for field in required:
        if field not in thesis:
            errors.append(f"Missing required field: {field}")

    direction = thesis.get("direction", "").upper()
    if direction and direction not in VALID_DIRECTIONS:
        errors.append(f"Invalid direction: {direction}. Valid: {VALID_DIRECTIONS}")

    horizon = thesis.get("time_horizon", "").upper()
    if horizon and horizon not in VALID_HORIZONS:
        errors.append(f"Invalid time_horizon: {horizon}. Valid: {VALID_HORIZONS}")

    conviction = thesis.get("conviction", 0)
    if isinstance(conviction, (int, float)):
        if conviction < 1 or conviction > 10:
            errors.append(f"conviction must be 1-10, got {conviction}")

    return errors


# ── Helpers ─────────────────────────────────────────────────────────────

import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "id") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
