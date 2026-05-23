"""CC-010 — Trend Line Breakout ML Classifier wrapper.

Implements the contract's lagged OLS support/resistance lines, base breakout
signal, and meta-label probability filter when a precomputed model probability
is supplied in enrichment data. This wrapper does not train a Random Forest.
"""

from __future__ import annotations

from typing import Any

from signals import register_signal
from signals._utils import atr, clamp_conviction, direction_from_int, extract_ohlcv


DEFAULT_LOOKBACK = 20
DEFAULT_ATR_PERIOD = 14
DEFAULT_THRESHOLD = 0.5


def _ols_line(values: list[float]) -> tuple[float, float]:
    """Return alpha, beta using contract OLS formula over i=0..L-1."""
    n = len(values)
    xbar = (n - 1) / 2.0
    ybar = sum(values) / n
    denom = sum((i - xbar) ** 2 for i in range(n))
    beta = 0.0 if denom == 0 else sum((i - xbar) * (y - ybar) for i, y in enumerate(values)) / denom
    alpha = ybar - beta * xbar
    return alpha, beta


def _trendlines(high: list[float], low: list[float], t: int, lookback: int) -> dict[str, float] | None:
    # Contract §2.1 uses high[t-L-1:t-1] / low[t-L-1:t-1], extended to x=L.
    start = t - lookback - 1
    end = t - 1
    if start < 0 or end <= start:
        return None
    highs = high[start:end]
    lows = low[start:end]
    if len(highs) != lookback or len(lows) != lookback:
        return None
    alpha_r, beta_r = _ols_line(highs)
    alpha_s, beta_s = _ols_line(lows)
    return {
        "resistance": alpha_r + beta_r * lookback,
        "support": alpha_s + beta_s * lookback,
        "resistance_alpha": alpha_r,
        "resistance_beta": beta_r,
        "support_alpha": alpha_s,
        "support_beta": beta_s,
    }


def cc010_signal(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Return latest CC-010 trend-line breakout after optional ML filter."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]))
    if n == 0:
        return None
    for key in ("high", "low", "close"):
        ohlcv[key] = ohlcv[key][-n:]
    if ohlcv["open"]:
        ohlcv["open"] = ohlcv["open"][-n:]

    lookback = int(enrich_data.get("cc010_lookback", DEFAULT_LOOKBACK))
    atr_period = int(enrich_data.get("cc010_atr_period", DEFAULT_ATR_PERIOD))
    threshold = float(enrich_data.get("cc010_ml_threshold", DEFAULT_THRESHOLD))
    t = n - 1
    if n < lookback + 2:
        return None

    lines = _trendlines(ohlcv["high"], ohlcv["low"], t, lookback)
    if lines is None:
        return None

    close_t = ohlcv["close"][t]
    base = 1 if close_t > lines["resistance"] else -1 if close_t < lines["support"] else 0
    if base == 0:
        return None

    atr_values = atr(ohlcv["high"], ohlcv["low"], ohlcv["close"], atr_period)
    atr_t = atr_values[t]
    if atr_t is not None and atr_t <= 0:
        return None

    ml_probability = (
        enrich_data.get("cc010_ml_probability")
        if "cc010_ml_probability" in enrich_data
        else enrich_data.get("ml_probability")
    )
    ml_active = ml_probability is not None
    prob = float(ml_probability) if ml_active else 0.5

    # Contract §2.3/§4: take base signal if f(X)>=theta; fade if f(X)<1-theta.
    filtered = base
    action = "BASE_SIGNAL_NO_MODEL"
    if ml_active:
        if prob >= threshold:
            filtered = base
            action = "ML_CONFIRMED_BREAKOUT"
        elif prob < (1.0 - threshold):
            filtered = -base
            action = "ML_FADE_FALSE_BREAKOUT"
        else:
            filtered = 0
            action = "ML_NEUTRAL_SKIP"
    if filtered == 0:
        return None

    breakout_ref = lines["resistance"] if base == 1 else lines["support"]
    breakout_ratio = (close_t - breakout_ref) / breakout_ref if breakout_ref else 0.0
    direction = direction_from_int(filtered)
    if ml_active:
        conviction = clamp_conviction(4.0 + 4.0 * abs(prob - 0.5) * 2.0 + min(2.0, abs(breakout_ratio) * 100.0))
    else:
        conviction = clamp_conviction(4.5 + min(3.0, abs(breakout_ratio) * 100.0))

    return {
        "signal": "CC010_TRENDLINE_BREAKOUT_ML",
        "direction": direction,
        "conviction": conviction,
        "reason": (
            f"Lagged OLS trend-line breakout: close={close_t:.4f}, support={lines['support']:.4f}, "
            f"resistance={lines['resistance']:.4f}; action={action}, p={prob:.3f}."
        ),
        "cc_ref": "CC-010",
        "metadata": {
            "ticker": ticker,
            "base_signal": base,
            "filtered_signal": filtered,
            "action": action,
            "ml_active": ml_active,
            "ml_probability": prob,
            "ml_threshold": threshold,
            "lookback": lookback,
            "atr_period": atr_period,
            "atr": atr_t,
            "breakout_ratio": breakout_ratio,
            **lines,
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "OLS high/low trendlines lagged one bar + RF meta-label probability filter",
        },
    }


register_signal(
    "CC-010",
    "Trend Line Breakout ML Classifier",
    "Lagged OLS support/resistance breakout with optional precomputed ML meta-label filter.",
    "CANDIDATE GENERATOR / FILTER",
    cc010_signal,
)
