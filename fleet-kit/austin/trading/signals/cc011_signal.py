"""CC-011 — Harmonic Pattern XABCD Scanner signal wrapper.

Implements the contract's XABCD pivot enumeration, Fibonacci ratio validation
with ±tolerance, and trade geometry for Gartley/Bat/Butterfly/Crab patterns.
"""

from __future__ import annotations

from typing import Any

from signals import register_signal
from signals._utils import atr, clamp_conviction, extract_ohlcv


Pivot = tuple[int, str, float]  # index, HIGH/LOW, price

PATTERN_SPECS: dict[str, dict[str, list[float | tuple[float, float]]]] = {
    "Gartley": {"xab": [0.618], "abc": [(0.382, 0.886)], "bcd": [(1.272, 1.618)], "xad": [0.786]},
    "Bat": {"xab": [(0.382, 0.500)], "abc": [(0.382, 0.886)], "bcd": [(1.618, 2.618)], "xad": [0.886]},
    "Butterfly": {"xab": [0.786], "abc": [(0.382, 0.886)], "bcd": [(1.618, 2.618)], "xad": [(1.272, 1.618)]},
    "Crab": {"xab": [(0.382, 0.618)], "abc": [(0.382, 0.886)], "bcd": [(2.240, 3.618)], "xad": [1.618]},
}


def _find_pivots(high: list[float], low: list[float], window: int, lookback: int) -> list[Pivot]:
    start = max(window, len(high) - lookback)
    end = len(high) - window
    pivots: list[Pivot] = []
    for i in range(start, end):
        if high[i] >= max(high[i - window : i]) and high[i] >= max(high[i + 1 : i + window + 1]):
            pivots.append((i, "HIGH", high[i]))
        if low[i] <= min(low[i - window : i]) and low[i] <= min(low[i + 1 : i + window + 1]):
            pivots.append((i, "LOW", low[i]))
    pivots.sort(key=lambda p: p[0])
    return _alternating_subset(pivots)


def _alternating_subset(pivots: list[Pivot]) -> list[Pivot]:
    out: list[Pivot] = []
    for p in pivots:
        if not out or p[1] != out[-1][1]:
            out.append(p)
            continue
        if p[1] == "HIGH" and p[2] > out[-1][2]:
            out[-1] = p
        elif p[1] == "LOW" and p[2] < out[-1][2]:
            out[-1] = p
    return out


def _compute_ratios(x: float, a: float, b: float, c: float, d: float) -> dict[str, float] | None:
    xa = abs(a - x)
    ab = abs(b - a)
    bc = abs(c - b)
    cd = abs(d - c)
    if min(xa, ab, bc) <= 0:
        return None
    return {
        "xab": ab / xa,
        "abc": bc / ab,
        "bcd": cd / bc,
        # Contract pitfall: XAD is measured from A toward X, not D-X.
        "xad": abs(d - a) / xa,
    }


def _match_error(observed: float, ideals: list[float | tuple[float, float]]) -> float:
    errors: list[float] = []
    for ideal in ideals:
        if isinstance(ideal, tuple):
            lo, hi = ideal
            if lo <= observed <= hi:
                errors.append(0.0)
            elif observed < lo:
                errors.append(abs(observed - lo) / lo)
            else:
                errors.append(abs(observed - hi) / hi)
        else:
            errors.append(abs(observed - ideal) / ideal)
    return min(errors) if errors else float("inf")


def _validate(ratios: dict[str, float], pattern_type: str, tolerance: float) -> dict[str, float] | None:
    spec = PATTERN_SPECS[pattern_type]
    scores = {leg: _match_error(ratios[leg], spec[leg]) for leg in ("xab", "abc", "bcd", "xad")}
    if all(err <= tolerance for err in scores.values()):
        return scores
    return None


def _trade_geometry(points: list[Pivot], orientation: str) -> dict[str, Any]:
    x, a, _b, _c, d = [p[2] for p in points]
    xa = abs(a - x)
    entry = d
    if orientation == "BULLISH":
        stop = x - 0.015 * abs(x)
        tps = [d + r * xa for r in (0.382, 0.618, 1.0)]
        direction = "LONG"
    else:
        stop = x + 0.015 * abs(x)
        tps = [d - r * xa for r in (0.382, 0.618, 1.0)]
        direction = "SHORT"
    return {"entry_price": entry, "stop_price": stop, "tp_levels": tps, "direction": direction}


def _scan_patterns(
    high: list[float], low: list[float], close: list[float], pivot_window: int, tolerance: float, min_leg_atr: float, lookback_bars: int
) -> tuple[list[dict[str, Any]], list[Pivot]]:
    pivots = _find_pivots(high, low, pivot_window, lookback_bars)
    if len(pivots) < 5:
        return [], pivots
    atr_values = atr(high, low, close, 14)
    latest_atr = next((v for v in reversed(atr_values) if v is not None and v > 0), None)
    patterns: list[dict[str, Any]] = []

    for i in range(len(pivots) - 4):
        points = pivots[i : i + 5]
        types = [p[1] for p in points]
        if types == ["LOW", "HIGH", "LOW", "HIGH", "LOW"]:
            orientation = "BULLISH"
        elif types == ["HIGH", "LOW", "HIGH", "LOW", "HIGH"]:
            orientation = "BEARISH"
        else:
            continue

        x, a, b, c, d = [p[2] for p in points]
        xa = abs(a - x)
        if latest_atr is not None and xa < min_leg_atr * latest_atr:
            continue
        ratios = _compute_ratios(x, a, b, c, d)
        if ratios is None:
            continue

        matches: list[dict[str, Any]] = []
        for pattern_type in PATTERN_SPECS:
            scores = _validate(ratios, pattern_type, tolerance)
            if scores is not None:
                matches.append({"type": pattern_type, "match_scores": scores, "total_error": sum(scores.values())})
        if not matches:
            continue
        best = min(matches, key=lambda m: m["total_error"])
        geometry = _trade_geometry(points, orientation)
        patterns.append(
            {
                **best,
                "orientation": orientation,
                "indices": {label: p[0] for label, p in zip(("X", "A", "B", "C", "D"), points)},
                "prices": {label: p[2] for label, p in zip(("X", "A", "B", "C", "D"), points)},
                "ratios": ratios,
                "xa_leg": xa,
                **geometry,
            }
        )
    return patterns, pivots


def cc011_signal(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Return the most recent valid harmonic XABCD pattern."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]))
    if n < 30:
        return None
    high, low, close = ohlcv["high"][-n:], ohlcv["low"][-n:], ohlcv["close"][-n:]

    pivot_window = int(enrich_data.get("cc011_pivot_window", 5))
    tolerance = float(enrich_data.get("cc011_tolerance", 0.05))
    min_leg_atr = float(enrich_data.get("cc011_min_leg_atr", 1.0))
    lookback_bars = int(enrich_data.get("cc011_lookback_bars", 300))
    if pivot_window < 3 or tolerance > 0.10:
        return None

    patterns, pivots = _scan_patterns(high, low, close, pivot_window, tolerance, min_leg_atr, lookback_bars)
    if not patterns:
        return None
    pattern = max(patterns, key=lambda p: p["indices"]["D"])
    quality = 1.0 - min(1.0, pattern["total_error"] / max(tolerance * 4.0, 1e-12))
    conviction = clamp_conviction(5.0 + 4.0 * quality + min(1.0, pattern["xa_leg"] / max(pattern["entry_price"], 1e-12)))

    return {
        "signal": "CC011_HARMONIC_XABCD",
        "direction": pattern["direction"],
        "conviction": conviction,
        "reason": (
            f"Valid {pattern['orientation']} {pattern['type']} XABCD harmonic pattern; "
            f"total_ratio_error={pattern['total_error']:.4f}, entry={pattern['entry_price']:.4f}."
        ),
        "cc_ref": "CC-011",
        "metadata": {
            "ticker": ticker,
            **pattern,
            "pivot_window": pivot_window,
            "tolerance": tolerance,
            "min_leg_atr": min_leg_atr,
            "lookback_bars": lookback_bars,
            "pivots_detected": len(pivots),
            "patterns_found": len(patterns),
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "XABCD ratios: xab=AB/XA, abc=BC/AB, bcd=CD/BC, xad=abs(D-A)/XA; all within tolerance",
        },
    }


register_signal(
    "CC-011",
    "Harmonic Pattern XABCD Scanner",
    "Gartley/Bat/Butterfly/Crab Fibonacci-ratio XABCD detector.",
    "CANDIDATE GENERATOR / ENTRY TIMING",
    cc011_signal,
)
