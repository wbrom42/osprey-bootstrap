"""
D-013 Layer 3: Verify Engine — Close the Prediction Loop

Every thesis that passes JUDGE registers a prediction. When its time window closes,
this engine checks actual price movement against the predicted direction.

Architecture: PREDICTION → VERIFY → SCORE → FEEDBACK
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def verify_thesis(thesis: dict, current_price: float, entry_price: float = None) -> dict:
    """
    Verify a thesis prediction against actual price movement.
    
    Args:
        thesis: The thesis record from pipeline output
        current_price: Current market price
        entry_price: Entry price at thesis generation time (if None, uses thesis price)
    
    Returns:
        Verification result with predicted vs actual, accuracy, and hit status
    """
    entry = entry_price or thesis.get("price_at_thesis", current_price)
    direction = thesis.get("direction", "LONG").upper()
    conviction = thesis.get("conviction", 0)
    horizon_days = thesis.get("time_horizon_days", 30)
    signal_source = thesis.get("signal_source", "unknown")
    
    # Calculate actual movement
    if entry and entry > 0:
        pct_change = ((current_price - entry) / entry) * 100
    else:
        pct_change = 0.0
    
    # Did the direction match?
    if direction == "LONG":
        correct_direction = pct_change > 0
    elif direction == "SHORT":
        correct_direction = pct_change < 0
    else:
        correct_direction = None
    
    # Magnitude scoring (0-1) — how strong was the conviction match?
    expected_magnitude = conviction_to_expected_pct(conviction)
    if expected_magnitude > 0:
        magnitude_score = min(1.0, abs(pct_change) / expected_magnitude)
    else:
        magnitude_score = 0.0
    
    verification = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "direction_correct": correct_direction,
        "pct_change": round(pct_change, 4),
        "predicted_direction": direction,
        "predicted_conviction": conviction,
        "entry_price": round(entry, 2) if entry else None,
        "current_price": round(current_price, 2),
        "magnitude_score": round(magnitude_score, 3),
        "signal_source": signal_source,
        "horizon_days": horizon_days,
        "hit": correct_direction is True,
    }
    
    return verification


def conviction_to_expected_pct(conviction: float) -> float:
    """Map conviction (1-10) to expected price movement percentage."""
    if conviction <= 3:
        return 1.0  # Low conviction: expect ~1% move
    elif conviction <= 5:
        return 2.5  # Medium: expect ~2.5%
    elif conviction <= 7:
        return 5.0  # High: expect ~5%
    elif conviction <= 9:
        return 8.0  # Very high: expect ~8%
    else:
        return 12.0  # Max conviction: expect ~12%


def verify_batch(predictions: list[dict], price_lookup: dict[str, float]) -> list[dict]:
    """
    Verify a batch of thesis predictions.
    
    Args:
        predictions: List of thesis records
        price_lookup: Dict of ticker → current_price
    
    Returns:
        List of verification results
    """
    results = []
    for thesis in predictions:
        ticker = thesis.get("ticker", "")
        current_price = price_lookup.get(ticker)
        if current_price is None:
            # Skip if we can't verify
            results.append({
                "ticker": ticker,
                "error": "price_unavailable",
                "verified_at": datetime.now(timezone.utc).isoformat()
            })
            continue
        verification = verify_thesis(thesis, current_price)
        verification["ticker"] = ticker
        verification["thesis_id"] = thesis.get("pipeline_id") or thesis.get("thesis_id", "")
        results.append(verification)
    
    return results
