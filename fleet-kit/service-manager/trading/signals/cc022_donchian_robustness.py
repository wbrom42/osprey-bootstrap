"""CC-022 — Donchian Parameter Robustness wrapper.

CC-022 is a validator-design concept for CC-001, not an independent trading
edge. This wrapper evaluates whether the latest Donchian direction is stable
across a sweep of lookback values and adjacent parameters. Because CC-001 failed
random-walk falsification, this wrapper also applies the same ordinal JSD
anti-noise gate before returning any directional result.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import permutations
from typing import Any, Iterable

import numpy as np

from .__init__ import register_signal


VALIDATOR_NOTE = (
    "CC-022 is a robustness validator for CC-001 parameters; it does not by "
    "itself validate or authorize the Donchian edge."
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

    aliases = ("close", "closes", "price", "prices", "c") if key == "close" else (key,)
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


def _entropy(probs: np.ndarray) -> float:
    probs = probs[probs > 0]
    if probs.size == 0:
        return 0.0
    return -float(np.sum(probs * np.log2(probs)))


def jsd_vs_uniform(series: np.ndarray, dimension: int = 3, mult: int = 28, delay: int = 1) -> float | None:
    k = math.factorial(dimension)
    lookback = k * mult
    if len(series) < lookback + (dimension - 1) * delay:
        return None
    patterns = _ordinal_patterns(series, dimension, delay)
    if len(patterns) < lookback:
        return None
    counts = Counter(patterns[-lookback:])
    p = np.asarray([counts.get(pattern, 0) / lookback for pattern in permutations(range(dimension))], dtype=float)
    u = np.full(k, 1.0 / k, dtype=float)
    m = 0.5 * (p + u)
    return float(np.clip(_entropy(m) - 0.5 * _entropy(p) - 0.5 * _entropy(u), 0.0, 1.0))


def donchian_raw_and_position(close: np.ndarray, lookback: int) -> tuple[int, int] | None:
    """Latest Donchian raw signal and forward-filled position for one lookback."""
    if lookback <= 0 or len(close) < lookback + 1:
        return None
    if not np.all(np.isfinite(close[-lookback - 1 :])):
        return None

    latest = close[-1]
    latest_window = close[-lookback - 1 : -1]
    raw = 1 if latest > np.max(latest_window) else -1 if latest < np.min(latest_window) else 0

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
    return int(raw), int(position)


def _agreement(values: list[int], direction: int) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value == direction) / len(values)


def robustness_snapshot(
    close: np.ndarray,
    sweep_min: int = 10,
    sweep_max: int = 500,
    sweep_step: int = 10,
    center_lookback: int = 72,
    neighbor_width: int = 20,
) -> dict | None:
    """Evaluate Donchian stability across sweep and adjacent parameters."""
    if sweep_min <= 0 or sweep_step <= 0 or sweep_max < sweep_min:
        raise ValueError("invalid sweep range")

    feasible_max = min(sweep_max, len(close) - 1)
    if feasible_max < sweep_min:
        return None

    lookbacks = list(range(sweep_min, feasible_max + 1, sweep_step))
    if center_lookback <= feasible_max and center_lookback not in lookbacks:
        lookbacks.append(center_lookback)
    lookbacks = sorted(set(lookbacks))

    raw_by_l: dict[int, int] = {}
    pos_by_l: dict[int, int] = {}
    for lookback in lookbacks:
        result = donchian_raw_and_position(close, lookback)
        if result is None:
            continue
        raw_by_l[lookback], pos_by_l[lookback] = result

    if not raw_by_l:
        return None

    center_result = donchian_raw_and_position(close, min(center_lookback, feasible_max))
    center_raw, center_pos = center_result if center_result is not None else (0, 0)
    target_direction = center_raw if center_raw != 0 else center_pos

    raw_nonzero = [value for value in raw_by_l.values() if value != 0]
    pos_nonzero = [value for value in pos_by_l.values() if value != 0]

    if target_direction == 0:
        long_fraction = _agreement(pos_nonzero, 1)
        short_fraction = _agreement(pos_nonzero, -1)
        if max(long_fraction, short_fraction) >= 0.70:
            target_direction = 1 if long_fraction > short_fraction else -1

    sweep_raw_agreement = _agreement(raw_nonzero, target_direction) if target_direction else 0.0
    sweep_position_agreement = _agreement(pos_nonzero, target_direction) if target_direction else 0.0

    neighbor_candidates = [
        center_lookback - neighbor_width,
        center_lookback - sweep_step,
        center_lookback,
        center_lookback + sweep_step,
        center_lookback + neighbor_width,
    ]
    neighbor_values: list[int] = []
    neighbor_positions: list[int] = []
    for lookback in sorted(set(l for l in neighbor_candidates if sweep_min <= l <= feasible_max)):
        result = donchian_raw_and_position(close, lookback)
        if result is not None:
            neighbor_values.append(result[0])
            neighbor_positions.append(result[1])

    adjacent_raw_agreement = _agreement([v for v in neighbor_values if v != 0], target_direction) if target_direction else 0.0
    adjacent_position_agreement = _agreement([v for v in neighbor_positions if v != 0], target_direction) if target_direction else 0.0

    return {
        "lookbacks": lookbacks,
        "raw_by_lookback": raw_by_l,
        "position_by_lookback": pos_by_l,
        "center_raw": center_raw,
        "center_position": center_pos,
        "target_direction": target_direction,
        "sweep_raw_agreement": sweep_raw_agreement,
        "sweep_position_agreement": sweep_position_agreement,
        "adjacent_raw_agreement": adjacent_raw_agreement,
        "adjacent_position_agreement": adjacent_position_agreement,
        "feasible_max": feasible_max,
    }


def cc022_donchian_robustness_signal(
    ticker: str,
    enrich_data: dict | None = None,
    price_data: dict | list | None = None,
) -> dict | None:
    """Signal interface wrapper for CC-022 robustness validation."""
    params = (enrich_data or {}).get("cc022", {}) if isinstance(enrich_data, dict) else {}
    sweep_min = int(params.get("sweep_min", 10))
    sweep_max = int(params.get("sweep_max", 500))
    sweep_step = int(params.get("sweep_step", 10))
    center = int(params.get("center_lookback", 72))
    neighbor_width = int(params.get("neighbor_width", 20))
    min_agreement = float(params.get("min_agreement", 0.70))
    jsd_threshold = float(params.get("jsd_threshold", 0.05))

    close = _series_from_data(price_data, "close")
    if close is None:
        close = _series_from_data(enrich_data, "close")
    if close is None:
        return None

    try:
        snapshot = robustness_snapshot(
            close,
            sweep_min=sweep_min,
            sweep_max=sweep_max,
            sweep_step=sweep_step,
            center_lookback=center,
            neighbor_width=neighbor_width,
        )
    except ValueError:
        return None
    if snapshot is None:
        return None

    jsd = jsd_vs_uniform(close)
    jsd_gate_pass = jsd is not None and jsd > jsd_threshold
    direction_value = int(snapshot["target_direction"])
    direction = "LONG" if direction_value > 0 else "SHORT" if direction_value < 0 else "NEUTRAL"

    robust = (
        direction_value != 0
        and snapshot["sweep_position_agreement"] >= min_agreement
        and max(snapshot["adjacent_raw_agreement"], snapshot["adjacent_position_agreement"]) >= min_agreement
        and jsd_gate_pass
    )

    if robust:
        signal_name = "DONCHIAN_PARAMETER_ROBUST_DIRECTION"
        conviction = 10.0 * min(snapshot["sweep_position_agreement"], max(snapshot["adjacent_raw_agreement"], snapshot["adjacent_position_agreement"]))
        reason = (
            f"{ticker}: Donchian {direction} direction is robust across parameter sweep "
            f"and adjacent lookbacks; JSD={jsd:.4f} passes gate."
        )
    elif not jsd_gate_pass:
        signal_name = "DONCHIAN_ROBUSTNESS_REJECTED_BY_JSD_GATE"
        direction = "NEUTRAL"
        conviction = 0.0
        reason = f"{ticker}: Donchian robustness suppressed because JSD gate failed ({jsd}). {VALIDATOR_NOTE}"
    else:
        signal_name = "DONCHIAN_PARAMETER_NOT_ROBUST"
        direction = "NEUTRAL"
        conviction = 2.0
        reason = f"{ticker}: Donchian direction did not meet {min_agreement:.0%} sweep/adjacent robustness threshold. {VALIDATOR_NOTE}"

    return {
        "signal": signal_name,
        "direction": direction,
        "conviction": float(np.clip(conviction, 0.0, 10.0)),
        "reason": reason,
        "cc_ref": "CC-022",
        "metadata": {
            "ticker": ticker,
            "validator_design_only": True,
            "note": VALIDATOR_NOTE,
            "sweep_min": sweep_min,
            "sweep_max": sweep_max,
            "sweep_step": sweep_step,
            "center_lookback": center,
            "neighbor_width": neighbor_width,
            "min_agreement": min_agreement,
            "jsd": jsd,
            "jsd_threshold": jsd_threshold,
            "jsd_gate_pass": jsd_gate_pass,
            "robust": robust,
            "target_direction": direction_value,
            "sweep_position_agreement": snapshot["sweep_position_agreement"],
            "sweep_raw_agreement": snapshot["sweep_raw_agreement"],
            "adjacent_position_agreement": snapshot["adjacent_position_agreement"],
            "adjacent_raw_agreement": snapshot["adjacent_raw_agreement"],
            "lookback_count": len(snapshot["lookbacks"]),
            "feasible_max_lookback": snapshot["feasible_max"],
            "boss_lane": "VALIDATOR / PARAMETER ROBUSTNESS",
            "caveats_required": [
                "corrected_significance",
                "adjacent_parameter_robustness",
                "out_of_sample_persistence",
                "effect_size_stability",
                "no_multiple_testing_artifact",
            ],
        },
    }


register_signal(
    cc_id="CC-022",
    name="Donchian Parameter Robustness Validator",
    description="Checks whether Donchian direction is stable across sweep and adjacent lookbacks; validator-design only.",
    lane="VALIDATOR / PARAMETER ROBUSTNESS",
    fn=cc022_donchian_robustness_signal,
    active=True,
)
