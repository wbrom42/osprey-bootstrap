"""CC-014 — Novel Chart Pattern Data Mining signal wrapper.

The contract's full training loop requires clustering and Monte Carlo validation.
This pure numpy wrapper implements the deterministic PIP extraction and current
pattern classification step against pre-trained cluster centers supplied through
enrichment data. It does not train KMeans or claim validation authority.
"""

from __future__ import annotations

from math import log
from typing import Any

import numpy as np

from signals import register_signal
from ._utils import clamp_conviction, direction_from_int, extract_ohlcv


def _pip_indices(values: np.ndarray, n_pips: int = 5) -> list[int]:
    if len(values) <= n_pips:
        return list(range(len(values)))
    selected = [0, len(values) - 1]
    xs = np.arange(len(values), dtype=float)
    while len(selected) < n_pips:
        selected.sort()
        best_idx = None
        best_dist = -1.0
        for left, right in zip(selected[:-1], selected[1:]):
            ax, ay = xs[left], values[left]
            bx, by = xs[right], values[right]
            denom = float(np.hypot(bx - ax, by - ay))
            if denom <= 0:
                continue
            for i in range(left + 1, right):
                if i in selected:
                    continue
                dist = abs((bx - ax) * (ay - values[i]) - (ax - xs[i]) * (by - ay)) / denom
                if dist > best_dist:
                    best_dist = float(dist)
                    best_idx = i
        if best_idx is None:
            break
        selected.append(best_idx)
    return sorted(selected)


def _zscore(values: np.ndarray) -> np.ndarray | None:
    mu = float(np.mean(values))
    sigma = float(np.std(values))
    if sigma <= 1e-12 or not np.isfinite(sigma):
        return None
    return (values - mu) / sigma


def _centers_from_enrich(enrich_data: dict[str, Any]) -> tuple[np.ndarray, int | None, int | None] | None:
    if "cc014_long_center" in enrich_data and "cc014_short_center" in enrich_data:
        centers = np.asarray([enrich_data["cc014_long_center"], enrich_data["cc014_short_center"]], dtype=float)
        return centers, 0, 1
    centers_raw = enrich_data.get("cc014_cluster_centers")
    if centers_raw is None:
        model = enrich_data.get("cc014_model")
        if isinstance(model, dict):
            centers_raw = model.get("cluster_centers")
    if centers_raw is None:
        return None
    centers = np.asarray(centers_raw, dtype=float)
    if centers.ndim != 2 or centers.shape[1] == 0:
        return None
    long_id = enrich_data.get("cc014_long_cluster_id")
    short_id = enrich_data.get("cc014_short_cluster_id")
    return centers, int(long_id) if long_id is not None else None, int(short_id) if short_id is not None else None


def cc014_signal(ticker: str, enrich_data: dict[str, Any] | None = None, price_data: Any = None) -> dict | None:
    """Classify the latest PIP pattern against supplied trained centers."""
    enrich_data = enrich_data or {}
    close = extract_ohlcv(price_data)["close"]
    lookback = int(enrich_data.get("cc014_lookback", 24))
    n_pips = int(enrich_data.get("cc014_n_pips", 5))
    if len(close) < lookback or n_pips < 3:
        return None
    prices = np.asarray(close[-lookback:], dtype=float)
    if not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        return None
    log_prices = np.asarray([log(float(p)) for p in prices], dtype=float)
    idx = _pip_indices(log_prices, n_pips)
    if len(idx) != n_pips:
        return None
    pips = log_prices[idx]
    pattern = _zscore(pips)
    if pattern is None:
        return None

    centers_pack = _centers_from_enrich(enrich_data)
    if centers_pack is None:
        return None
    centers, long_id, short_id = centers_pack
    if centers.shape[1] != len(pattern):
        return None
    distances = np.linalg.norm(centers - pattern, axis=1)
    nearest = int(np.argmin(distances))
    if long_id is not None and nearest == long_id:
        raw = 1
    elif short_id is not None and nearest == short_id:
        raw = -1
    else:
        return None
    nearest_dist = float(distances[nearest])
    other_best = float(np.partition(distances, 1)[1]) if len(distances) > 1 else nearest_dist
    separation = max(0.0, other_best - nearest_dist)
    conviction = clamp_conviction(4.0 + min(4.0, separation * 2.0) + min(2.0, 1.0 / max(nearest_dist, 1e-9)))

    return {
        "signal": "CC014_PIP_PATTERN_CLUSTER",
        "direction": direction_from_int(raw),
        "conviction": conviction,
        "reason": f"Latest {n_pips}-PIP normalized pattern is nearest to trained {'long' if raw > 0 else 'short'} cluster {nearest}; distance={nearest_dist:.4f}.",
        "cc_ref": "CC-014",
        "metadata": {
            "ticker": ticker,
            "pip_indices": [int(i) for i in idx],
            "pip_values_z": [float(x) for x in pattern],
            "nearest_cluster_id": nearest,
            "long_cluster_id": long_id,
            "short_cluster_id": short_id,
            "nearest_distance": nearest_dist,
            "distance_separation": separation,
            "lookback": lookback,
            "n_pips": n_pips,
            "requires_pretrained_centers": True,
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "PIPs by max perpendicular distance; zscore(PIPs); nearest Euclidean distance to trained long/short centers",
        },
    }


register_signal(
    "CC-014",
    "Novel Chart Pattern Data Mining",
    "PIP pattern classifier using pre-trained cluster centers supplied in enrichment data.",
    "CANDIDATE GENERATOR / FEATURE GENERATOR",
    cc014_signal,
)
