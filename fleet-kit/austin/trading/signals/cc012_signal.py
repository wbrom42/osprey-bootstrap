"""CC-012 — Market Profile Support/Resistance signal wrapper.

Pure numpy implementation of the contract's volume-at-price histogram, Point of
Control, Value Area, and HVN/LVN classification. The wrapper emits a directional
signal only when the latest close breaks outside the computed value area; inside
value it remains non-actionable.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from signals import register_signal
from ._utils import clamp_conviction, direction_from_int, extract_ohlcv


def _volume_profile(
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    bucket_size: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    if high.size == 0 or low.size == 0 or volume.size == 0 or bucket_size <= 0:
        return None
    lo = float(np.floor(np.nanmin(low) / bucket_size) * bucket_size)
    hi = float(np.ceil(np.nanmax(high) / bucket_size) * bucket_size)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi < lo:
        return None
    bucket_count = int(round((hi - lo) / bucket_size)) + 1
    if bucket_count <= 0 or bucket_count > 50_000:
        return None
    prices = lo + np.arange(bucket_count, dtype=float) * bucket_size
    vols = np.zeros(bucket_count, dtype=float)

    for h, l, v in zip(high, low, volume):
        if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(v)) or v <= 0:
            continue
        bar_lo = float(np.floor(min(l, h) / bucket_size) * bucket_size)
        bar_hi = float(np.ceil(max(l, h) / bucket_size) * bucket_size)
        start = max(0, int(round((bar_lo - lo) / bucket_size)))
        end = min(bucket_count - 1, int(round((bar_hi - lo) / bucket_size)))
        n = max(1, end - start + 1)
        vols[start : end + 1] += float(v) / n
    if float(np.sum(vols)) <= 0:
        return None
    return prices, vols


def _value_area(prices: np.ndarray, vols: np.ndarray, pct: float) -> dict[str, Any]:
    poc_idx = int(np.argmax(vols))
    target = float(np.sum(vols) * pct)
    accum = float(vols[poc_idx])
    left = right = poc_idx
    while accum < target and (left > 0 or right < len(vols) - 1):
        left_vol = float(vols[left - 1]) if left > 0 else -1.0
        right_vol = float(vols[right + 1]) if right < len(vols) - 1 else -1.0
        if left_vol >= right_vol and left > 0:
            left -= 1
            accum += max(0.0, left_vol)
        elif right < len(vols) - 1:
            right += 1
            accum += max(0.0, right_vol)
        else:
            break
    mean_v = float(np.mean(vols)) if vols.size else 0.0
    hvn = prices[vols > mean_v * 1.5].tolist() if mean_v > 0 else []
    lvn = prices[vols < mean_v * 0.5].tolist() if mean_v > 0 else []
    return {
        "poc": float(prices[poc_idx]),
        "vah": float(prices[right]),
        "val": float(prices[left]),
        "hvn": [float(x) for x in hvn],
        "lvn": [float(x) for x in lvn],
        "total_volume": float(np.sum(vols)),
        "mean_bucket_volume": mean_v,
        "poc_volume": float(vols[poc_idx]),
        "bucket_count": int(len(prices)),
        "value_area_volume_pct": float(accum / max(np.sum(vols), 1e-12)),
    }


def cc012_signal(ticker: str, enrich_data: dict[str, Any] | None = None, price_data: Any = None) -> dict | None:
    """Return a VAH/VAL breakout signal from the latest market profile."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["high"]), len(ohlcv["low"]), len(ohlcv["close"]), len(ohlcv["volume"]))
    lookback = int(enrich_data.get("cc012_lookback_bars", 390))
    if n < max(5, min(lookback, 20)):
        return None
    high = np.asarray(ohlcv["high"][-min(n, lookback) :], dtype=float)
    low = np.asarray(ohlcv["low"][-min(n, lookback) :], dtype=float)
    close = np.asarray(ohlcv["close"][-min(n, lookback) :], dtype=float)
    volume = np.asarray(ohlcv["volume"][-min(n, lookback) :], dtype=float)

    raw_bucket = enrich_data.get("cc012_bucket_size")
    if raw_bucket is None:
        median_range = float(np.nanmedian(np.maximum(high - low, 0.0))) if high.size else 0.0
        bucket_size = max(float(enrich_data.get("cc012_min_bucket", 0.01)), median_range / 10.0 if median_range > 0 else 0.25)
    else:
        bucket_size = float(raw_bucket)
    value_area_pct = float(enrich_data.get("cc012_value_area_pct", 0.70))
    value_area_pct = min(0.90, max(0.50, value_area_pct))

    profile = _volume_profile(high, low, volume, bucket_size)
    if profile is None:
        return None
    prices, vols = profile
    levels = _value_area(prices, vols, value_area_pct)
    latest = float(close[-1])
    raw = 1 if latest > levels["vah"] else -1 if latest < levels["val"] else 0
    if raw == 0:
        return None

    boundary = levels["vah"] if raw > 0 else levels["val"]
    distance_buckets = abs(latest - boundary) / max(bucket_size, 1e-12)
    poc_strength = levels["poc_volume"] / max(levels["mean_bucket_volume"], 1e-12)
    conviction = clamp_conviction(4.0 + min(3.0, distance_buckets) + min(3.0, poc_strength / 2.0))

    return {
        "signal": "CC012_MARKET_PROFILE_VALUE_AREA_BREAK",
        "direction": direction_from_int(raw),
        "conviction": conviction,
        "reason": f"Latest close {latest:.4f} broke {'above VAH' if raw > 0 else 'below VAL'} ({boundary:.4f}); POC={levels['poc']:.4f}.",
        "cc_ref": "CC-012",
        "metadata": {
            "ticker": ticker,
            **levels,
            "latest_close": latest,
            "bucket_size": bucket_size,
            "lookback_bars": int(min(n, lookback)),
            "value_area_pct": value_area_pct,
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "Uniform bar volume distributed across price buckets; POC=max V(p); VA expands from POC to target volume.",
        },
    }


register_signal(
    "CC-012",
    "Market Profile Support/Resistance",
    "Volume-at-price profile with POC, value area, and VAH/VAL breakout wrapper.",
    "REGIME CONTEXT / CANDIDATE GENERATOR",
    cc012_signal,
)
