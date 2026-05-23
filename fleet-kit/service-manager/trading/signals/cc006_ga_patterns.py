"""CC-006 — Genetic Algorithm Candlestick Pattern Recognition wrapper.

This wrapper evaluates already-evolved GA candlestick patterns supplied in
``enrich_data``. It implements the contract predicate directly:
P(c[t-w+1]..c[t]) = AND_i R_i(...), then forms the ensemble mean signal across
matching top patterns. It does not train a GA in-session.
"""

from __future__ import annotations

import operator
from statistics import mean
from typing import Any

from signals import register_signal
from signals._utils import clamp_conviction, direction_from_int, extract_ohlcv, signed


_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    "=": operator.eq,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
    "!=": operator.ne,
}


def _bar(ohlcv: dict[str, list[float]], idx: int) -> dict[str, float]:
    o = ohlcv["open"][idx]
    h = ohlcv["high"][idx]
    l = ohlcv["low"][idx]
    c = ohlcv["close"][idx]
    rng = max(0.0, h - l)
    body = abs(o - c)
    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "body": body,
        "upper_wick": h - max(o, c),
        "lower_wick": min(o, c) - l,
        "range": rng,
        "direction": float(signed(c - o)),
        "pct_body": body / rng if rng > 0 else 0.0,
    }


def _resolve_expr(expr: Any, window_bars: list[dict[str, float]]) -> float:
    """Resolve a rule expression from the CC-006 grammar.

    Supported forms:
    - numeric constant: 1.5
    - string current-candle feature: "body", "direction", "range"
    - dict: {"feature":"body", "index":-1}
    - dict: {"feature":"rel_body", "left_index":-1, "right_index":-2}
    - dict: {"feature":"rolling_mean", "of":"body"}
    """
    if isinstance(expr, (int, float)):
        return float(expr)
    if isinstance(expr, str):
        return float(window_bars[-1].get(expr, 0.0))
    if not isinstance(expr, dict):
        return 0.0

    feature = str(expr.get("feature", expr.get("name", ""))).lower()
    idx = int(expr.get("index", -1))

    def get_bar(i: int) -> dict[str, float]:
        return window_bars[i]

    if feature in {"open", "high", "low", "close", "body", "upper_wick", "lower_wick", "range", "direction", "pct_body"}:
        return float(get_bar(idx).get(feature, 0.0))
    if feature in {"rel_body", "rel_range"}:
        left = int(expr.get("left_index", -1))
        right = int(expr.get("right_index", -2))
        base = "body" if feature == "rel_body" else "range"
        denom = get_bar(right).get(base, 0.0)
        return float(get_bar(left).get(base, 0.0) / denom) if denom else 0.0
    if feature in {"rolling_mean", "mean"}:
        field = str(expr.get("of", "body"))
        vals = [b.get(field, 0.0) for b in window_bars]
        return float(mean(vals)) if vals else 0.0
    return 0.0


def _rule_passes(rule: dict[str, Any], window_bars: list[dict[str, float]]) -> bool:
    # Flexible rule schema for evolved patterns.
    left = rule.get("left", rule.get("lhs", rule.get("expr1")))
    right = rule.get("right", rule.get("rhs", rule.get("expr2")))
    op = str(rule.get("op", rule.get("operator", ">")))
    if left is None:
        left = {"feature": rule.get("feature", "direction"), "index": rule.get("index", -1)}
    if right is None:
        right = float(rule.get("threshold", 0.0))
    fn = _OPS.get(op)
    if fn is None:
        return False
    return bool(fn(_resolve_expr(left, window_bars), _resolve_expr(right, window_bars)))


def _evaluate_pattern(pattern: dict[str, Any], ohlcv: dict[str, list[float]]) -> int:
    window = int(pattern.get("window", pattern.get("w", 2)))
    if window < 1 or len(ohlcv["close"]) < window:
        return 0
    start = len(ohlcv["close"]) - window
    window_bars = [_bar(ohlcv, i) for i in range(start, len(ohlcv["close"]))]
    rules = pattern.get("rules", [])
    if not rules or not all(isinstance(r, dict) and _rule_passes(r, window_bars) for r in rules):
        return 0

    # Contract §2: match direction follows current candle close-vs-open.
    return signed(window_bars[-1]["close"] - window_bars[-1]["open"])


def cc006_ga_patterns(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Evaluate supplied evolved candlestick patterns and return ensemble signal."""
    enrich_data = enrich_data or {}
    patterns = (
        enrich_data.get("cc006_patterns")
        or enrich_data.get("ga_patterns")
        or enrich_data.get("evolved_patterns")
        or []
    )
    if not isinstance(patterns, list) or not patterns:
        return None

    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["open"]), len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]))
    if n < 2:
        return None
    for key in ("open", "high", "low", "close"):
        ohlcv[key] = ohlcv[key][-n:]

    top_n = int(enrich_data.get("cc006_top_n", 5))
    selected = [p for p in patterns[:top_n] if isinstance(p, dict)]
    signals = [_evaluate_pattern(p, ohlcv) for p in selected]
    matched = [s for s in signals if s != 0]
    if not matched:
        return None

    ensemble = sum(signals) / max(1, len(selected))
    direction = direction_from_int(1 if ensemble > 0 else -1 if ensemble < 0 else 0)
    conviction = clamp_conviction(4.0 + 4.0 * abs(ensemble) + min(2.0, len(matched) / max(1, len(selected)) * 2.0))

    return {
        "signal": "CC006_GA_CANDLESTICK_ENSEMBLE",
        "direction": direction,
        "conviction": conviction,
        "reason": (
            f"{len(matched)}/{len(selected)} supplied evolved candlestick pattern(s) matched; "
            f"ensemble_signal={ensemble:.3f}. Requires OOS/noise validation before trading use."
        ),
        "cc_ref": "CC-006",
        "metadata": {
            "ticker": ticker,
            "patterns_evaluated": len(selected),
            "patterns_matched": len(matched),
            "pattern_signals": signals,
            "ensemble_signal": ensemble,
            "rule_formula": "P(window)=AND_i R_i; ensemble=mean(signal_i)",
            "requires_supplied_ga_patterns": True,
            "validation_status": "DEPLOYED_PAPER_BOUNDED_BUILD_AUTH_IN_CONTRACT",
        },
    }


register_signal(
    "CC-006",
    "GA Candlestick Pattern Recognition",
    "Evaluates supplied genetically evolved OHLC relationship-rule patterns and ensembles matches.",
    "CANDIDATE GENERATOR / SYNTHESIS",
    cc006_ga_patterns,
)
