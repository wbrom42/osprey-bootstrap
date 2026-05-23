"""CC-001 — Modified Donchian Channel Breakout with mandatory JSD gate.

The underlying Donchian concept was falsified on random-walk data. This wrapper
therefore refuses to emit a directional breakout unless a Jensen-Shannon
Divergence (JSD) ordinal-regime gate shows the recent series is distinguishable
from a uniform/random ordinal-pattern distribution.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import permutations
from typing import Any, Iterable

import numpy as np

from .__init__ import register_signal


FALSIFICATION_NOTE = (
    "CC-001 failed random-walk falsification; directional output is gated by "
    "JSD vs uniform ordinal-pattern distribution."
)


def _to_float_array(values: Iterable[Any]) -> np.ndarray | None:
    try:
        arr = np.asarray(list(values), dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 1 or arr.size == 0:
        return None
    return arr


def _series_from_data(data: Any, key: str = "close") -> np.ndarray | None:
    if data is None:
        return None

    aliases = {
        "close": ("close", "closes", "price", "prices", "c"),
    }.get(key, (key,))

    if isinstance(data, dict):
        for candidate in aliases:
            if candidate in data and data[candidate] is not None:
                return _to_float_array(data[candidate])
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


def _ordinal_patterns(series: np.ndarray, dimension: int, delay: int) -> list[tuple[int, ...]]:
    max_start = len(series) - (dimension - 1) * delay
    patterns: list[tuple[int, ...]] = []
    for start in range(max_start):
        window = series[start : start + dimension * delay : delay]
        if len(window) != dimension or not np.all(np.isfinite(window)):
            continue
        patterns.append(tuple(np.argsort(window, kind="mergesort").tolist()))
    return patterns


def _shannon_entropy(probs: np.ndarray) -> float:
    probs = probs[probs > 0.0]
    if probs.size == 0:
        return 0.0
    return -float(np.sum(probs * np.log2(probs)))


def jsd_uniform_ordinal_gate(
    series: np.ndarray,
    dimension: int = 3,
    mult: int = 28,
    delay: int = 1,
) -> tuple[float | None, bool, dict]:
    """JSD(P || U) where P is recent ordinal-pattern distribution and U uniform.

    This implements the anti-noise principle required by the CC-001 patch:
    only act when the current ordinal regime is distinguishable from random.
    """
    if dimension < 2 or mult <= 0 or delay < 1:
        raise ValueError("dimension >= 2, mult > 0, delay >= 1 required")

    k = math.factorial(dimension)
    lookback = k * mult
    required_points = lookback + (dimension - 1) * delay
    if len(series) < required_points:
        return None, False, {"reason": "insufficient_data", "required_points": required_points}

    patterns = _ordinal_patterns(series, dimension, delay)
    if len(patterns) < lookback:
        return None, False, {"reason": "insufficient_valid_patterns", "required_patterns": lookback}

    recent = patterns[-lookback:]
    counts = Counter(recent)
    all_patterns = list(permutations(range(dimension)))
    p = np.asarray([counts.get(pattern, 0) / lookback for pattern in all_patterns], dtype=float)
    u = np.full(k, 1.0 / k, dtype=float)
    m = 0.5 * (p + u)

    jsd = _shannon_entropy(m) - 0.5 * _shannon_entropy(p) - 0.5 * _shannon_entropy(u)
    # log2 JSD is bounded by 1.0 bit; clip small negative floating error.
    jsd = float(np.clip(jsd, 0.0, 1.0))
    return jsd, True, {"lookback_patterns": lookback, "pattern_count": k}


def donchian_latest(close: np.ndarray, lookback: int) -> tuple[int, int, float, float, float]:
    """Return latest raw signal, forward-filled position, close, upper, lower."""
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    if len(close) < lookback + 1:
        raise ValueError("insufficient close history for Donchian lookback")

    latest_close = float(close[-1])
    window = close[-lookback - 1 : -1]
    if not np.isfinite(latest_close) or not np.all(np.isfinite(window)):
        raise ValueError("non-finite close value in Donchian window")

    upper = float(np.max(window))
    lower = float(np.min(window))
    raw_signal = 1 if latest_close > upper else -1 if latest_close < lower else 0

    position = 0
    for idx in range(lookback, len(close)):
        hist_window = close[idx - lookback : idx]
        c = close[idx]
        if not np.isfinite(c) or not np.all(np.isfinite(hist_window)):
            continue
        if c > np.max(hist_window):
            position = 1
        elif c < np.min(hist_window):
            position = -1

    return raw_signal, position, latest_close, upper, lower


def cc001_donchian_signal(
    ticker: str,
    enrich_data: dict | None = None,
    price_data: dict | list | None = None,
) -> dict | None:
    """Signal interface wrapper for CC-001."""
    params = (enrich_data or {}).get("cc001", {}) if isinstance(enrich_data, dict) else {}
    lookback = int(params.get("lookback", params.get("N", 72)))
    jsd_threshold = float(params.get("jsd_threshold", 0.05))
    jsd_dimension = int(params.get("jsd_dimension", 3))
    jsd_mult = int(params.get("jsd_mult", 28))
    jsd_delay = int(params.get("jsd_delay", 1))

    close = _series_from_data(price_data, "close")
    if close is None:
        close = _series_from_data(enrich_data, "close")
    if close is None:
        return None
    if len(close) < max(lookback + 1, math.factorial(jsd_dimension) * jsd_mult + (jsd_dimension - 1) * jsd_delay):
        return None

    try:
        raw_signal, position, latest_close, upper, lower = donchian_latest(close, lookback)
    except ValueError:
        return None

    jsd, _, jsd_meta = jsd_uniform_ordinal_gate(close, jsd_dimension, jsd_mult, jsd_delay)
    gate_pass = jsd is not None and jsd > jsd_threshold

    channel_width = max(upper - lower, 1e-12)
    if raw_signal == 1:
        breakout_strength = max(0.0, (latest_close - upper) / channel_width)
    elif raw_signal == -1:
        breakout_strength = max(0.0, (lower - latest_close) / channel_width)
    else:
        breakout_strength = 0.0

    metadata = {
        "ticker": ticker,
        "lookback": lookback,
        "latest_close": latest_close,
        "upper": upper,
        "lower": lower,
        "raw_signal": raw_signal,
        "position": position,
        "breakout_strength": breakout_strength,
        "jsd": jsd,
        "jsd_threshold": jsd_threshold,
        "jsd_gate_pass": gate_pass,
        "jsd_gate": jsd_meta,
        "falsification_status": "FALSIFIED_RANDOM_WALK_PATCHED_WITH_JSD_GATE",
        "boss_lane": "CANDIDATE GENERATOR / ENTRY TIMING",
        "warning": FALSIFICATION_NOTE,
    }

    if not gate_pass:
        return {
            "signal": "DONCHIAN_BREAKOUT_REJECTED_BY_JSD_GATE",
            "direction": "NEUTRAL",
            "conviction": 0.0,
            "reason": f"{ticker}: Donchian output suppressed; JSD regime gate failed ({jsd}). {FALSIFICATION_NOTE}",
            "cc_ref": "CC-001",
            "metadata": metadata,
        }

    if raw_signal == 0:
        return {
            "signal": "DONCHIAN_NO_BREAKOUT",
            "direction": "NEUTRAL",
            "conviction": 1.0,
            "reason": f"{ticker}: no strict close-only Donchian breakout at N={lookback}; JSD gate passes.",
            "cc_ref": "CC-001",
            "metadata": metadata,
        }

    assert jsd is not None  # for type checkers; gate_pass guarantees this branch
    direction = "LONG" if raw_signal > 0 else "SHORT"
    conviction = 5.0 + min(3.0, breakout_strength * 10.0) + min(2.0, (jsd - jsd_threshold) / max(jsd_threshold, 1e-9))
    return {
        "signal": "DONCHIAN_BREAKOUT_WITH_JSD_GATE",
        "direction": direction,
        "conviction": float(np.clip(conviction, 0.0, 10.0)),
        "reason": (
            f"{ticker}: close {latest_close:.6g} {'>' if raw_signal > 0 else '<'} "
            f"Donchian {'upper' if raw_signal > 0 else 'lower'} "
            f"({upper:.6g}/{lower:.6g}); JSD={jsd:.4f} > {jsd_threshold:.4f}."
        ),
        "cc_ref": "CC-001",
        "metadata": metadata,
    }


register_signal(
    cc_id="CC-001",
    name="Modified Donchian Channel Breakout (JSD-gated)",
    description="Close-only lagged Donchian breakout; directional output requires JSD anti-random-walk regime gate.",
    lane="CANDIDATE GENERATOR / ENTRY TIMING",
    fn=cc001_donchian_signal,
    active=True,
)
