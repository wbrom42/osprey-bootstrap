"""Shared utilities for D-013 NeuroTrader signal wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from statistics import median
from typing import Any


_COLUMN_ALIASES = {
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c", "adj_close", "adjclose"),
    "volume": ("volume", "vol", "v"),
    "timestamp": ("timestamp", "datetime", "date", "time", "ts"),
}


def _lower_key_map(obj: Mapping[str, Any]) -> dict[str, str]:
    return {str(k).lower(): k for k in obj.keys()}


def _lookup_mapping(obj: Mapping[str, Any], canonical: str) -> Any:
    lower = _lower_key_map(obj)
    for alias in _COLUMN_ALIASES[canonical]:
        if alias in lower:
            return obj[lower[alias]]
    return None


def _to_float_list(values: Any) -> list[float]:
    if values is None:
        return []
    # pandas Series / numpy arrays expose tolist().
    if hasattr(values, "tolist"):
        values = values.tolist()
    out: list[float] = []
    for value in values:
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(f):
            out.append(f)
    return out


def _to_list(values: Any) -> list[Any]:
    if values is None:
        return []
    if hasattr(values, "tolist"):
        return values.tolist()
    return list(values)


def extract_ohlcv(price_data: Any) -> dict[str, list[Any]]:
    """Extract OHLCV arrays from a DataFrame, mapping-of-arrays, or list-of-bars.

    Supports canonical columns (open/high/low/close/volume/timestamp) and compact
    aliases (o/h/l/c/v). Unknown or non-finite numeric values are skipped per
    column; callers should verify that required arrays have adequate length.
    """
    if price_data is None:
        return {k: [] for k in ("open", "high", "low", "close", "volume", "timestamp")}

    # pandas-like DataFrame.
    if hasattr(price_data, "columns"):
        cols = {str(c).lower(): c for c in price_data.columns}
        result: dict[str, list[Any]] = {}
        for canonical in ("open", "high", "low", "close", "volume"):
            col = next((cols[a] for a in _COLUMN_ALIASES[canonical] if a in cols), None)
            result[canonical] = _to_float_list(price_data[col]) if col is not None else []
        ts_col = next((cols[a] for a in _COLUMN_ALIASES["timestamp"] if a in cols), None)
        if ts_col is not None:
            result["timestamp"] = _to_list(price_data[ts_col])
        elif hasattr(price_data, "index"):
            result["timestamp"] = _to_list(price_data.index)
        else:
            result["timestamp"] = []
        return result

    # Mapping of columns/arrays.
    if isinstance(price_data, Mapping):
        return {
            "open": _to_float_list(_lookup_mapping(price_data, "open")),
            "high": _to_float_list(_lookup_mapping(price_data, "high")),
            "low": _to_float_list(_lookup_mapping(price_data, "low")),
            "close": _to_float_list(_lookup_mapping(price_data, "close")),
            "volume": _to_float_list(_lookup_mapping(price_data, "volume")),
            "timestamp": _to_list(_lookup_mapping(price_data, "timestamp")),
        }

    # List of bar mappings.
    if isinstance(price_data, Sequence) and not isinstance(price_data, (str, bytes)):
        bars = list(price_data)
        result = {k: [] for k in ("open", "high", "low", "close", "volume", "timestamp")}
        for bar in bars:
            if not isinstance(bar, Mapping):
                continue
            for canonical in ("open", "high", "low", "close", "volume"):
                value = _lookup_mapping(bar, canonical)
                try:
                    f = float(value)
                except (TypeError, ValueError):
                    continue
                if isfinite(f):
                    result[canonical].append(f)
            ts = _lookup_mapping(bar, "timestamp")
            if ts is not None:
                result["timestamp"].append(ts)
        return result

    return {k: [] for k in ("open", "high", "low", "close", "volume", "timestamp")}


def direction_from_int(value: int | float) -> str:
    if value > 0:
        return "LONG"
    if value < 0:
        return "SHORT"
    return "NEUTRAL"


def signed(value: float, eps: float = 1e-12) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def clamp_conviction(value: float) -> float:
    return round(max(0.0, min(10.0, float(value))), 2)


def rolling_median(values: list[float], window: int, end: int | None = None) -> float | None:
    """Median of values[max(0,end-window):end], excluding the current bar by default."""
    if end is None:
        end = len(values)
    start = max(0, end - window)
    chunk = [v for v in values[start:end] if v > 0 and isfinite(v)]
    if not chunk:
        return None
    return float(median(chunk))


def parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    # pandas Timestamp supports to_pydatetime().
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime()
        except Exception:
            pass
    if isinstance(value, (int, float)):
        try:
            # Accept seconds or milliseconds.
            if value > 10_000_000_000:
                value = value / 1000.0
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def atr(high: list[float], low: list[float], close: list[float], period: int = 14) -> list[float | None]:
    n = min(len(high), len(low), len(close))
    trs: list[float] = []
    out: list[float | None] = [None] * n
    for i in range(n):
        if i == 0:
            tr = high[i] - low[i]
        else:
            tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        trs.append(tr)
        if i + 1 >= period:
            out[i] = sum(trs[i + 1 - period : i + 1]) / period
    return out
