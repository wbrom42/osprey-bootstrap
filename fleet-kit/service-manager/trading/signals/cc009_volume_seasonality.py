"""CC-009 — Crypto Bot Volume Seasonality wrapper.

Implements the contract formulas for volume normalization, first-minute bot
consensus, and liquidity timing. Per task context, this concept is marked as
FALSIFIED on real 1-minute data; it is registered inactive and returns only a
non-actionable diagnostic with zero conviction.
"""

from __future__ import annotations

from math import log
from statistics import mean
from typing import Any

from signals import register_signal
from signals._utils import direction_from_int, extract_ohlcv, parse_timestamp, rolling_median, signed


DEFAULT_ROLLING_MEDIAN_DAYS = 30
BARS_PER_DAY_1MIN = 24 * 60


def _normalized_volume_at(volumes: list[float], idx: int, window_bars: int) -> float | None:
    med = rolling_median(volumes, window_bars, end=idx)
    if med is None or med <= 0 or volumes[idx] <= 0:
        return None
    return log(volumes[idx] / med)


def _seasonal_expected(
    v_norm: list[float | None], timestamps: list[Any], latest_idx: int, hour: int, minute: int
) -> float:
    exact: list[float] = []
    same_minute: list[float] = []
    for i in range(latest_idx):
        val = v_norm[i]
        if val is None:
            continue
        ts = parse_timestamp(timestamps[i]) if i < len(timestamps) else None
        if ts is None:
            continue
        if ts.minute == minute:
            same_minute.append(float(val))
            if ts.hour == hour:
                exact.append(float(val))
    if exact:
        return float(mean(exact))
    if same_minute:
        return float(mean(same_minute))
    return 0.0


def cc009_volume_seasonality(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Return the latest :00 first-minute consensus diagnostic if available."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    n = min(len(ohlcv["open"]), len(ohlcv["close"]), len(ohlcv["volume"]))
    if n < 2 or len(ohlcv["timestamp"]) < n:
        return None

    for key in ("open", "close", "volume", "timestamp"):
        ohlcv[key] = ohlcv[key][-n:]

    latest_idx = n - 1
    latest_ts = parse_timestamp(ohlcv["timestamp"][latest_idx])
    if latest_ts is None or latest_ts.minute != 0:
        return None

    rolling_days = int(enrich_data.get("cc009_rolling_median_days", DEFAULT_ROLLING_MEDIAN_DAYS))
    window_bars = max(1, rolling_days * BARS_PER_DAY_1MIN)
    if latest_idx < window_bars:
        return None

    v_norm: list[float | None] = [None] * n
    # Contract §4 Algorithm 1: V'_t = ln(volume / rolling_median).
    for i in range(window_bars, n):
        v_norm[i] = _normalized_volume_at(ohlcv["volume"], i, window_bars)

    latest_norm = v_norm[latest_idx]
    if latest_norm is None:
        return None

    # Contract §2.3: psi_h = sign(close_h - open_h) on the first-minute bar.
    psi = signed(ohlcv["close"][latest_idx] - ohlcv["open"][latest_idx])
    expected = _seasonal_expected(v_norm, ohlcv["timestamp"], latest_idx, latest_ts.hour, latest_ts.minute)
    liquidity_score = latest_norm - expected
    direction = direction_from_int(psi)

    return {
        "signal": "CC009_VOLUME_SEASONALITY_DIAGNOSTIC",
        "direction": direction,
        "conviction": 0.0,
        "reason": (
            f"FALSIFIED on real 1-min data per task context; diagnostic only. "
            f"At :00, psi=sign(close-open)={psi}, V'={latest_norm:.4f}, L={liquidity_score:.4f}."
        ),
        "cc_ref": "CC-009",
        "metadata": {
            "ticker": ticker,
            "validation_status": "FALSIFIED_REAL_1MIN_DATA",
            "active_for_trading": False,
            "timestamp": str(ohlcv["timestamp"][latest_idx]),
            "normalized_volume": latest_norm,
            "seasonal_expected": expected,
            "liquidity_timing_score": liquidity_score,
            "bot_consensus_psi": psi,
            "rolling_median_days": rolling_days,
            "formulae": {
                "normalized_volume": "ln(V_t / median(V_{t-30D:t}))",
                "consensus": "psi_h = sign(close_h - open_h)",
                "liquidity": "L_t = V'_t - expected(V'_t | seasonal average)",
            },
            "caveat": "Concept retained for provenance/diagnostics only; do not use for candidate generation.",
        },
    }


register_signal(
    "CC-009",
    "Volume Seasonality",
    "Inactive diagnostic wrapper for :00 volume normalization and first-minute bot consensus; falsified on real 1-min data.",
    "EXECUTION TIMING / RESEARCH ONLY",
    cc009_volume_seasonality,
    active=False,
)
