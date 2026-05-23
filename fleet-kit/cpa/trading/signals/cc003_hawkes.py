"""CC-003 — Hawkes Process Volatility Exit.

Implements the NeuroTrader math contract with numpy/stdlib only:
- norm_range_t = (ln(H_t) - ln(L_t)) / ATR(N)_t
- intensity_t = intensity_{t-1} * exp(-kappa) + norm_range_t
- v_hawk_t = intensity_t * kappa
- exit when v_hawk_t < rolling Q05_t
- first re-entry when v_hawk crosses above rolling Q95 after a quiet period
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

from .__init__ import register_signal


def _to_float_array(values: Iterable[Any]) -> np.ndarray | None:
    try:
        arr = np.asarray(list(values), dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 1 or arr.size == 0:
        return None
    return arr


def _series_from_data(data: Any, key: str) -> np.ndarray | None:
    if data is None:
        return None

    aliases = {
        "open": ("open", "opens", "o"),
        "high": ("high", "highs", "h"),
        "low": ("low", "lows", "l"),
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

    return None


def _get_ohlc(price_data: Any, enrich_data: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    high = _series_from_data(price_data, "high")
    low = _series_from_data(price_data, "low")
    close = _series_from_data(price_data, "close")
    if high is None:
        high = _series_from_data(enrich_data, "high")
    if low is None:
        low = _series_from_data(enrich_data, "low")
    if close is None:
        close = _series_from_data(enrich_data, "close")
    if high is None or low is None or close is None:
        return None
    n = min(len(high), len(low), len(close))
    if n == 0:
        return None
    return high[-n:], low[-n:], close[-n:]


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 336) -> np.ndarray:
    """Wilder RMA ATR on raw prices, matching the contract's reference behavior."""
    if length <= 0:
        raise ValueError("ATR length must be positive")
    n = len(close)
    tr = np.full(n, np.nan, dtype=float)
    for idx in range(n):
        if not (np.isfinite(high[idx]) and np.isfinite(low[idx]) and np.isfinite(close[idx])):
            continue
        if idx == 0 or not np.isfinite(close[idx - 1]):
            tr[idx] = high[idx] - low[idx]
        else:
            tr[idx] = max(high[idx] - low[idx], abs(high[idx] - close[idx - 1]), abs(low[idx] - close[idx - 1]))

    atr = np.full(n, np.nan, dtype=float)
    finite_seen = 0
    prev_atr = math.nan
    for idx, value in enumerate(tr):
        if not np.isfinite(value):
            continue
        finite_seen += 1
        if finite_seen < length:
            # Warm-up RMA from first observation; quantile logic still waits for enough bars.
            prev_atr = value if not np.isfinite(prev_atr) else ((prev_atr * (finite_seen - 1)) + value) / finite_seen
        elif finite_seen == length:
            start = max(0, idx - length + 1)
            seed = tr[start : idx + 1]
            prev_atr = float(np.nanmean(seed))
        else:
            prev_atr = ((prev_atr * (length - 1)) + value) / length
        atr[idx] = prev_atr
    return atr


def hawkes_volatility_state(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    kappa: float = 0.1,
    atr_length: int = 336,
    quantile_lookback: int = 168,
) -> dict | None:
    """Compute the CC-003 Hawkes state machine over all supplied bars."""
    if kappa <= 0.0:
        raise ValueError("kappa must be positive")
    if atr_length <= 0 or quantile_lookback <= 1:
        raise ValueError("atr_length > 0 and quantile_lookback > 1 required")

    n = min(len(high), len(low), len(close))
    if n < max(atr_length, quantile_lookback) + 1:
        return None
    high, low, close = high[-n:], low[-n:], close[-n:]

    atr = wilder_atr(high, low, close, atr_length)
    norm_range = np.full(n, np.nan, dtype=float)
    for idx in range(n):
        if high[idx] > 0 and low[idx] > 0 and atr[idx] > 0:
            norm_range[idx] = (math.log(high[idx]) - math.log(low[idx])) / atr[idx]

    alpha = math.exp(-kappa)
    intensity = np.full(n, np.nan, dtype=float)
    v_hawk = np.full(n, np.nan, dtype=float)
    last_intensity = math.nan
    for idx, value in enumerate(norm_range):
        if not np.isfinite(value):
            if np.isfinite(last_intensity):
                intensity[idx] = last_intensity
                v_hawk[idx] = last_intensity * kappa
            continue
        last_intensity = value if not np.isfinite(last_intensity) else last_intensity * alpha + value
        intensity[idx] = last_intensity
        v_hawk[idx] = last_intensity * kappa

    q05 = np.full(n, np.nan, dtype=float)
    q95 = np.full(n, np.nan, dtype=float)
    for idx in range(quantile_lookback - 1, n):
        window = v_hawk[idx - quantile_lookback + 1 : idx + 1]
        if np.all(np.isfinite(window)):
            q05[idx] = float(np.percentile(window, 5, method="linear"))
            q95[idx] = float(np.percentile(window, 95, method="linear"))

    signal_state = np.zeros(n, dtype=int)
    last_quiet = -1
    entry_trigger = np.zeros(n, dtype=bool)
    exit_trigger = np.zeros(n, dtype=bool)

    for idx in range(1, n):
        signal_state[idx] = signal_state[idx - 1]
        if not (np.isfinite(v_hawk[idx]) and np.isfinite(q05[idx]) and np.isfinite(q95[idx])):
            continue

        if v_hawk[idx] < q05[idx]:
            signal_state[idx] = 0
            last_quiet = idx
            exit_trigger[idx] = True
            continue

        first_cross = (
            v_hawk[idx] > q95[idx]
            and np.isfinite(v_hawk[idx - 1])
            and np.isfinite(q95[idx - 1])
            and v_hawk[idx - 1] <= q95[idx - 1]
        )
        if first_cross and last_quiet > 0:
            delta = close[idx] - close[last_quiet]
            if delta > 0:
                signal_state[idx] = 1
                entry_trigger[idx] = True
            elif delta < 0:
                signal_state[idx] = -1
                entry_trigger[idx] = True

    return {
        "norm_range": norm_range,
        "intensity": intensity,
        "v_hawk": v_hawk,
        "q05": q05,
        "q95": q95,
        "signal_state": signal_state,
        "entry_trigger": entry_trigger,
        "exit_trigger": exit_trigger,
        "last_quiet": last_quiet,
        "alpha": alpha,
    }


def cc003_hawkes_signal(
    ticker: str,
    enrich_data: dict | None = None,
    price_data: dict | list | None = None,
) -> dict | None:
    """Signal interface wrapper for CC-003."""
    params = (enrich_data or {}).get("cc003", {}) if isinstance(enrich_data, dict) else {}
    kappa = float(params.get("kappa", 0.1))
    atr_length = int(params.get("atr_length", params.get("N", 336)))
    q_lookback = int(params.get("quantile_lookback", params.get("lookback", 168)))

    ohlc = _get_ohlc(price_data, enrich_data)
    if ohlc is None:
        return None
    high, low, close = ohlc

    try:
        state = hawkes_volatility_state(high, low, close, kappa=kappa, atr_length=atr_length, quantile_lookback=q_lookback)
    except ValueError:
        return None
    if state is None:
        return None

    idx = len(close) - 1
    v = float(state["v_hawk"][idx])
    q05 = float(state["q05"][idx])
    q95 = float(state["q95"][idx])
    current_state = int(state["signal_state"][idx])
    did_exit = bool(state["exit_trigger"][idx])
    did_enter = bool(state["entry_trigger"][idx])

    if not (np.isfinite(v) and np.isfinite(q05) and np.isfinite(q95)):
        return None

    if did_exit:
        signal_name = "HAWKES_VOLATILITY_EXIT"
        direction = "NEUTRAL"
        gap = max(0.0, (q05 - v) / max(q05, 1e-12))
        conviction = 7.0 + min(3.0, gap * 10.0)
        reason = f"{ticker}: Hawkes intensity {v:.6g} dropped below Q05 {q05:.6g}; volatility exhaustion exit."
    elif did_enter:
        signal_name = "HAWKES_VOLATILITY_REENTRY"
        direction = "LONG" if current_state > 0 else "SHORT"
        gap = max(0.0, (v - q95) / max(q95, 1e-12))
        conviction = 6.0 + min(4.0, gap * 10.0)
        reason = f"{ticker}: Hawkes intensity {v:.6g} first-crossed above Q95 {q95:.6g} after quiet period."
    else:
        signal_name = "HAWKES_VOLATILITY_HOLD"
        direction = "LONG" if current_state > 0 else "SHORT" if current_state < 0 else "NEUTRAL"
        conviction = 3.0 if direction == "NEUTRAL" else 5.0
        reason = f"{ticker}: no current Hawkes exit/re-entry trigger; state={direction}, v_hawk={v:.6g}."

    return {
        "signal": signal_name,
        "direction": direction,
        "conviction": float(np.clip(conviction, 0.0, 10.0)),
        "reason": reason,
        "cc_ref": "CC-003",
        "metadata": {
            "ticker": ticker,
            "norm_range": float(state["norm_range"][idx]) if np.isfinite(state["norm_range"][idx]) else None,
            "v_hawk": v,
            "q05": q05,
            "q95": q95,
            "state": current_state,
            "entry_trigger": did_enter,
            "exit_trigger": did_exit,
            "last_quiet": int(state["last_quiet"]),
            "kappa": kappa,
            "alpha": float(state["alpha"]),
            "atr_length": atr_length,
            "quantile_lookback": q_lookback,
            "boss_lane": "EXIT MANAGEMENT / REGIME DETECTION",
        },
    }


register_signal(
    cc_id="CC-003",
    name="Hawkes Process Volatility Exit",
    description="Self-exciting volatility intensity for quiet-period exits and first-cross re-entry timing.",
    lane="EXIT MANAGEMENT / REGIME DETECTION",
    fn=cc003_hawkes_signal,
    active=True,
)
