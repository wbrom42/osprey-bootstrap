"""CC-002 — Permutation Entropy Regime Filter.

Pure numpy/stdlib wrapper for the NeuroTrader math contract:
    PE = -sum(p(pi_j) * log2(p(pi_j))) / log2(d!)

Low PE indicates a structured regime. High PE indicates a noisy/random regime.
This is a regime/filter signal, not a directional long/short trigger.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

import numpy as np

from .__init__ import register_signal


def _series_from_data(data: Any, key: str) -> np.ndarray | None:
    """Extract a numeric series from dict/list-shaped price/enrichment data."""
    if data is None:
        return None

    aliases = {
        "close": ("close", "closes", "price", "prices", "c"),
        "volume": ("volume", "volumes", "vol", "v"),
    }.get(key, (key,))

    if isinstance(data, dict):
        for candidate in aliases:
            if candidate in data and data[candidate] is not None:
                return _to_float_array(data[candidate])
        # Some callers nest OHLCV data under a common key.
        for nested_key in ("ohlcv", "bars", "candles", "data"):
            if nested_key in data:
                nested = _series_from_data(data[nested_key], key)
                if nested is not None:
                    return nested
        return None

    if isinstance(data, (list, tuple)) and data:
        first = data[0]
        if isinstance(first, dict):
            values = []
            for row in data:
                value = None
                for candidate in aliases:
                    if candidate in row:
                        value = row[candidate]
                        break
                values.append(value)
            return _to_float_array(values)
        if key == "close":
            return _to_float_array(data)

    return None


def _to_float_array(values: Iterable[Any]) -> np.ndarray | None:
    try:
        arr = np.asarray(list(values), dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 1 or arr.size == 0:
        return None
    return arr


def _ordinal_patterns(series: np.ndarray, dimension: int, delay: int) -> list[tuple[int, ...]]:
    """Return ordinal patterns pi_i = argsort([x_i, x_{i+tau}, ...])."""
    max_start = len(series) - (dimension - 1) * delay
    patterns: list[tuple[int, ...]] = []
    for start in range(max_start):
        window = series[start : start + dimension * delay : delay]
        if len(window) != dimension or not np.all(np.isfinite(window)):
            continue
        # Stable mergesort gives deterministic tie handling.
        patterns.append(tuple(np.argsort(window, kind="mergesort").tolist()))
    return patterns


def permutation_entropy(
    series: np.ndarray,
    dimension: int = 3,
    mult: int = 28,
    delay: int = 1,
) -> float | None:
    """Compute latest normalized permutation entropy per CC-002."""
    if dimension < 2 or mult <= 0 or delay < 1:
        raise ValueError("dimension >= 2, mult > 0, and delay >= 1 are required")

    pattern_count = math.factorial(dimension)
    lookback = pattern_count * mult
    required_points = lookback + (dimension - 1) * delay
    if len(series) < required_points:
        return None

    patterns = _ordinal_patterns(series, dimension, delay)
    if len(patterns) < lookback:
        return None

    counts = Counter(patterns[-lookback:])
    probs = np.asarray([count / lookback for count in counts.values() if count > 0], dtype=float)
    if probs.size == 0:
        return None

    entropy = -float(np.sum(probs * np.log2(probs)))
    max_entropy = math.log2(pattern_count)
    if max_entropy <= 0:
        return None
    return float(np.clip(entropy / max_entropy, 0.0, 1.0))


def _regime_from_pe(pe_price: float, pe_volume: float | None = None) -> tuple[str, bool, float]:
    """Classify PE using contract thresholds and return regime/gate/conviction."""
    if pe_price < 0.50:
        regime = "structured"
    elif pe_price > 0.85:
        regime = "random"
    else:
        regime = "transition"

    dual_pass = pe_volume is not None and pe_price < 0.65 and pe_volume < 0.65
    entry_gate_pass = pe_price < 0.70

    if dual_pass:
        conviction = 9.0
    elif pe_price < 0.50:
        conviction = 8.0
    elif entry_gate_pass:
        conviction = 6.0
    elif pe_price > 0.85:
        conviction = 2.0
    else:
        conviction = 4.0

    return regime, entry_gate_pass, conviction


def permutation_entropy_signal(
    ticker: str,
    enrich_data: dict | None = None,
    price_data: dict | list | None = None,
) -> dict | None:
    """Signal interface wrapper for CC-002."""
    params = (enrich_data or {}).get("cc002", {}) if isinstance(enrich_data, dict) else {}
    dimension = int(params.get("dimension", params.get("d", 3)))
    mult = int(params.get("mult", 28))
    delay = int(params.get("delay", params.get("tau", 1)))

    close = _series_from_data(price_data, "close")
    if close is None:
        close = _series_from_data(enrich_data, "close")
    if close is None:
        return None

    pe_price = permutation_entropy(close, dimension=dimension, mult=mult, delay=delay)
    if pe_price is None:
        return None

    volume = _series_from_data(price_data, "volume")
    if volume is None:
        volume = _series_from_data(enrich_data, "volume")
    pe_volume = None
    if volume is not None:
        pe_volume = permutation_entropy(volume, dimension=dimension, mult=mult, delay=delay)

    regime, gate_pass, conviction = _regime_from_pe(pe_price, pe_volume)
    dual_filter_pass = pe_volume is not None and pe_price < 0.65 and pe_volume < 0.65

    if regime == "structured":
        signal_name = "PERMUTATION_ENTROPY_STRUCTURED_REGIME"
        reason = f"{ticker}: low permutation entropy PE_price={pe_price:.3f}; structured regime."
    elif regime == "random":
        signal_name = "PERMUTATION_ENTROPY_RANDOM_REGIME"
        reason = f"{ticker}: high permutation entropy PE_price={pe_price:.3f}; noisy/random regime."
    else:
        signal_name = "PERMUTATION_ENTROPY_TRANSITION_REGIME"
        reason = f"{ticker}: intermediate permutation entropy PE_price={pe_price:.3f}; transition regime."

    if pe_volume is not None:
        reason += f" PE_volume={pe_volume:.3f}."
    if dual_filter_pass:
        reason += " Dual price/volume filter passes (<0.65 both)."

    return {
        "signal": signal_name,
        "direction": "NEUTRAL",
        "conviction": float(np.clip(conviction, 0.0, 10.0)),
        "reason": reason,
        "cc_ref": "CC-002",
        "metadata": {
            "ticker": ticker,
            "pe_price": pe_price,
            "pe_volume": pe_volume,
            "regime": regime,
            "entry_filter_pass": gate_pass,
            "dual_filter_pass": dual_filter_pass,
            "dimension": dimension,
            "mult": mult,
            "lookback_patterns": math.factorial(dimension) * mult,
            "delay": delay,
            "boss_lane": "REGIME CONTEXT / FILTER",
            "note": "Permutation entropy is not directional; use only as a regime/filter overlay.",
        },
    }


register_signal(
    cc_id="CC-002",
    name="Permutation Entropy Regime Filter",
    description="Low normalized permutation entropy identifies structured regimes; high PE identifies noisy/random regimes.",
    lane="REGIME CONTEXT / FILTER",
    fn=permutation_entropy_signal,
    active=True,
)
