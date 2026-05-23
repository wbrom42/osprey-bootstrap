"""CC-015 — Automated Price Trend Lines signal wrapper.

Implements the contract's OLS seed, pivot-anchored validity-constrained support
and resistance lines, and finite-difference slope optimization. Emits a regime
signal when both optimized slopes agree.
"""

from __future__ import annotations

from math import log
from typing import Any

import numpy as np

from signals import register_signal
from ._utils import clamp_conviction, direction_from_int, extract_ohlcv


def _ols(values: np.ndarray) -> tuple[float, float]:
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    return float(slope), float(intercept)


def _line_error(slope: float, pivot: int, data: np.ndarray, support: bool, eps: float = 1e-10) -> float:
    intercept = -slope * pivot + float(data[pivot])
    x = np.arange(len(data), dtype=float)
    line = slope * x + intercept
    if support:
        if np.any(line > data + eps):
            return float("inf")
    else:
        if np.any(line < data - eps):
            return float("inf")
    return float(np.sum((line - data) ** 2))


def _optimize_slope(data: np.ndarray, pivot: int, init_slope: float, support: bool) -> tuple[float, float, bool]:
    if len(data) < 2:
        return 0.0, float(data[0]) if len(data) else 0.0, False
    best = float(init_slope)
    best_err = _line_error(best, pivot, data, support)
    if not np.isfinite(best_err):
        # Find a valid seed by scanning a local slope band.
        scale = max(float(np.std(data)), 1e-6) / max(len(data), 1)
        candidates = np.linspace(init_slope - 10 * scale, init_slope + 10 * scale, 101)
        for cand in candidates:
            err = _line_error(float(cand), pivot, data, support)
            if err < best_err:
                best, best_err = float(cand), err
    step = max(abs(init_slope) * 0.25, max(float(np.std(data)), 1e-6) / max(len(data), 1))
    while step >= 0.0001:
        improved = False
        for cand in (best - step, best + step):
            err = _line_error(cand, pivot, data, support)
            if err < best_err:
                best, best_err = float(cand), err
                improved = True
        if not improved:
            step *= 0.5
    intercept = -best * pivot + float(data[pivot])
    return best, intercept, bool(np.isfinite(best_err))


def _fit_trendlines(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, Any] | None:
    if len(close) < 3:
        return None
    seed_slope, seed_intercept = _ols(close)
    x = np.arange(len(close), dtype=float)
    seed_line = seed_slope * x + seed_intercept
    upper_pivot = int(np.argmax(high - seed_line))
    lower_pivot = int(np.argmin(low - seed_line))
    support_slope, support_intercept, support_valid = _optimize_slope(low, lower_pivot, seed_slope, True)
    resist_slope, resist_intercept, resist_valid = _optimize_slope(high, upper_pivot, seed_slope, False)
    return {
        "seed_slope": seed_slope,
        "seed_intercept": seed_intercept,
        "upper_pivot": upper_pivot,
        "lower_pivot": lower_pivot,
        "support_slope": support_slope,
        "support_intercept": support_intercept,
        "support_valid": support_valid,
        "resistance_slope": resist_slope,
        "resistance_intercept": resist_intercept,
        "resistance_valid": resist_valid,
    }


def cc015_signal(ticker: str, enrich_data: dict[str, Any] | None = None, price_data: Any = None) -> dict | None:
    """Return a trend regime signal from optimized support/resistance slopes."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]))
    lookback = int(enrich_data.get("cc015_lookback", 30))
    if n < max(lookback, 10):
        return None
    high = np.asarray(ohlcv["high"][-lookback:], dtype=float)
    low = np.asarray(ohlcv["low"][-lookback:], dtype=float)
    close = np.asarray(ohlcv["close"][-lookback:], dtype=float)
    log_transform = bool(enrich_data.get("cc015_log_transform", True))
    if log_transform:
        if np.any(high <= 0) or np.any(low <= 0) or np.any(close <= 0):
            return None
        high = np.asarray([log(float(x)) for x in high], dtype=float)
        low = np.asarray([log(float(x)) for x in low], dtype=float)
        close = np.asarray([log(float(x)) for x in close], dtype=float)
    if not (np.all(np.isfinite(high)) and np.all(np.isfinite(low)) and np.all(np.isfinite(close))):
        return None

    fit = _fit_trendlines(high, low, close)
    if fit is None:
        return None
    threshold = float(enrich_data.get("cc015_slope_threshold", 0.0))
    support_slope = float(fit["support_slope"])
    resist_slope = float(fit["resistance_slope"])
    raw = 1 if support_slope > threshold and resist_slope > threshold else -1 if support_slope < -threshold and resist_slope < -threshold else 0
    if raw == 0:
        return None
    slope_mag = (abs(support_slope) + abs(resist_slope)) / 2.0
    agreement = 1.0 - min(1.0, abs(support_slope - resist_slope) / max(abs(support_slope), abs(resist_slope), 1e-12))
    conviction = clamp_conviction(4.0 + min(3.0, slope_mag * 1000.0) + 3.0 * agreement)

    return {
        "signal": "CC015_OPTIMIZED_TRENDLINE_SLOPE_REGIME",
        "direction": direction_from_int(raw),
        "conviction": conviction,
        "reason": f"Optimized support/resistance slopes agree: support={support_slope:.6f}, resistance={resist_slope:.6f}.",
        "cc_ref": "CC-015",
        "metadata": {
            "ticker": ticker,
            **fit,
            "lookback": lookback,
            "log_transform": log_transform,
            "slope_threshold": threshold,
            "slope_agreement": agreement,
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "OLS seed -> extreme-deviation pivots -> validity-constrained slope error minimization",
        },
    }


register_signal(
    "CC-015",
    "Automated Price Trend Lines",
    "Pivot-anchored validity-constrained support/resistance trend line slope regime.",
    "REGIME CONTEXT / FEATURE GENERATOR",
    cc015_signal,
)
