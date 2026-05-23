"""CC-013 — Volume Spread Analysis signal wrapper.

Implements the contract's ATR/range normalization, rolling volume median,
rolling OLS regression of normalized range on normalized volume, quality gates,
and latest deviation oscillator.
"""

from __future__ import annotations

from statistics import median
from typing import Any

import numpy as np

from signals import register_signal
from ._utils import clamp_conviction, direction_from_int, extract_ohlcv


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = min(len(high), len(low), len(close))
    tr = np.zeros(n, dtype=float)
    for i in range(n):
        if i == 0:
            tr[i] = high[i] - low[i]
        else:
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan, dtype=float)
    if n >= period:
        out[period - 1] = float(np.mean(tr[:period]))
        for i in range(period, n):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def _rolling_median_array(values: np.ndarray, lookback: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=float)
    for i in range(lookback, len(values)):
        window = [float(v) for v in values[i - lookback : i] if np.isfinite(v) and v > 0]
        if window:
            out[i] = float(median(window))
    return out


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float] | None:
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 3 or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    xbar = float(np.mean(x))
    ybar = float(np.mean(y))
    denom = float(np.sum((x - xbar) ** 2))
    if denom <= 0:
        return None
    slope = float(np.sum((x - xbar) * (y - ybar)) / denom)
    intercept = ybar - slope * xbar
    r = float(np.corrcoef(x, y)[0, 1])
    return slope, intercept, r


def cc013_signal(ticker: str, enrich_data: dict[str, Any] | None = None, price_data: Any = None) -> dict | None:
    """Return latest extreme VSA deviation, using candle direction for context."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]), len(ohlcv["volume"]))
    if n < 60:
        return None
    high = np.asarray(ohlcv["high"][-n:], dtype=float)
    low = np.asarray(ohlcv["low"][-n:], dtype=float)
    close = np.asarray(ohlcv["close"][-n:], dtype=float)
    volume = np.asarray(ohlcv["volume"][-n:], dtype=float)
    open_ = np.asarray(ohlcv["open"][-n:], dtype=float) if len(ohlcv["open"]) >= n else close.copy()

    lookback = int(enrich_data.get("cc013_norm_lookback", 168))
    lookback = max(20, min(lookback, max(20, n // 2)))
    r_threshold = float(enrich_data.get("cc013_r_threshold", 0.2))
    signal_threshold = float(enrich_data.get("cc013_signal_threshold", 0.9))

    atr = _wilder_atr(high, low, close, 14)
    range_norm = np.where(atr > 1e-12, np.minimum((high - low) / atr, 20.0), np.nan)
    vol_med = _rolling_median_array(volume, lookback)
    vol_norm = np.where(vol_med > 1e-12, volume / vol_med, np.nan)

    t = n - 1
    if t < max(lookback * 2, 50):
        return None
    regression = _ols(vol_norm[t - lookback + 1 : t + 1], range_norm[t - lookback + 1 : t + 1])
    if regression is None:
        return None
    slope, intercept, r = regression
    if slope <= 0 or r < r_threshold or not np.isfinite(range_norm[t]) or not np.isfinite(vol_norm[t]):
        return None
    predicted = intercept + slope * float(vol_norm[t])
    deviation = float(range_norm[t] - predicted)
    if abs(deviation) < signal_threshold:
        return None

    candle_move = float(close[t] - open_[t]) if np.isfinite(open_[t]) else float(close[t] - close[t - 1])
    candle_dir = 1 if candle_move > 0 else -1 if candle_move < 0 else 0
    raw = candle_dir if deviation > 0 else -candle_dir
    if raw == 0:
        raw = 1 if close[t] > close[t - 1] else -1 if close[t] < close[t - 1] else 0
    label = "EFFORTLESS_MOVE" if deviation > 0 else "ABSORPTION"
    conviction = clamp_conviction(4.0 + min(3.0, abs(deviation)) + min(3.0, max(0.0, r) * 3.0))

    return {
        "signal": f"CC013_VSA_{label}",
        "direction": direction_from_int(raw),
        "conviction": conviction,
        "reason": f"VSA {label.lower()}: deviation={deviation:.4f}, r={r:.3f}, slope={slope:.4f}; direction uses latest candle context.",
        "cc_ref": "CC-013",
        "metadata": {
            "ticker": ticker,
            "deviation": deviation,
            "predicted_range_norm": float(predicted),
            "range_norm": float(range_norm[t]),
            "volume_norm": float(vol_norm[t]),
            "slope": slope,
            "intercept": intercept,
            "r": r,
            "r_threshold": r_threshold,
            "signal_threshold": signal_threshold,
            "norm_lookback": lookback,
            "context_direction_rule": "positive deviation follows candle move; negative deviation fades candle move",
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "deviation = R'_t - (alpha + beta V'_t), gated by beta>0 and r>=threshold",
        },
    }


register_signal(
    "CC-013",
    "Volume Spread Analysis",
    "ATR/volume-normalized range-vs-volume regression deviation oscillator.",
    "FEATURE GENERATOR / ENTRY TIMING",
    cc013_signal,
)
