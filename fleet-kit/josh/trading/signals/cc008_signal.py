"""CC-008 — Head & Shoulders Pattern Recognition signal wrapper.

Implements the math contract's deterministic geometric H&S/IHS detector:
rolling-window pivots, 5-extrema validation, neckline, break confirmation, and
trade geometry metadata.
"""

from __future__ import annotations

from math import log
from typing import Any

from signals import register_signal
from signals._utils import clamp_conviction, extract_ohlcv


Pivot = tuple[int, int, float]  # index, type (+1 top / -1 bottom), price


def _series(close: list[float], log_prices: bool) -> list[float]:
    if log_prices and all(p > 0 for p in close):
        return [log(p) for p in close]
    return list(close)


def _find_pivots(close: list[float], order: int) -> list[Pivot]:
    pivots: list[Pivot] = []
    n = len(close)
    for k in range(order, n - order):
        left = close[k - order : k]
        right = close[k + 1 : k + order + 1]
        if close[k] >= max(left) and close[k] >= max(right):
            pivots.append((k, 1, close[k]))
        if close[k] <= min(left) and close[k] <= min(right):
            pivots.append((k, -1, close[k]))
    pivots.sort(key=lambda p: p[0])
    return _alternating_subset(pivots)


def _alternating_subset(pivots: list[Pivot]) -> list[Pivot]:
    out: list[Pivot] = []
    for pivot in pivots:
        if not out or pivot[1] != out[-1][1]:
            out.append(pivot)
            continue
        # Consecutive same-type extrema: retain the more extreme pivot.
        if pivot[1] == 1 and pivot[2] > out[-1][2]:
            out[-1] = pivot
        elif pivot[1] == -1 and pivot[2] < out[-1][2]:
            out[-1] = pivot
    return out


def _neckline(e1: Pivot, e3: Pivot, idx: int) -> float:
    if e3[0] == e1[0]:
        return e1[2]
    slope = (e3[2] - e1[2]) / (e3[0] - e1[0])
    return e1[2] + slope * (idx - e1[0])


def _pattern_r2(close: list[float], extrema: list[Pivot]) -> float | None:
    xs = [p[0] for p in extrema]
    ys = [p[2] for p in extrema]
    start, end = xs[0], xs[-1]
    if end <= start + 1:
        return None
    fitted: list[float] = []
    actual: list[float] = []
    for seg in range(len(xs) - 1):
        x0, x1 = xs[seg], xs[seg + 1]
        y0, y1 = ys[seg], ys[seg + 1]
        for x in range(x0, x1 + (1 if seg == len(xs) - 2 else 0)):
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            fitted.append(y0 + t * (y1 - y0))
            actual.append(close[x])
    if not actual:
        return None
    y_mean = sum(actual) / len(actual)
    ss_tot = sum((y - y_mean) ** 2 for y in actual)
    ss_res = sum((a - f) ** 2 for a, f in zip(actual, fitted))
    return 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))


def _validate(extrema: list[Pivot], close: list[float], break_idx: int, inverted: bool, symmetry_ratio: float, use_balance: bool) -> dict | None:
    e0, e1, e2, e3, e4 = extrema
    # Rule 1: head dominance.
    if not inverted:
        if not (e2[2] > e0[2] and e2[2] > e4[2]):
            return None
    else:
        if not (e2[2] < e0[2] and e2[2] < e4[2]):
            return None

    # Rule 2: balance.
    if use_balance:
        if not inverted:
            if not (e0[2] > (e3[2] + e4[2]) / 2.0 and e4[2] > (e1[2] + e0[2]) / 2.0):
                return None
        else:
            if not (e0[2] < (e3[2] + e4[2]) / 2.0 and e4[2] < (e1[2] + e0[2]) / 2.0):
                return None

    # Rule 3: symmetry.
    left_span = abs(e2[0] - e0[0])
    right_span = abs(e4[0] - e2[0])
    if left_span == 0 or right_span == 0:
        return None
    if left_span > symmetry_ratio * right_span or right_span > symmetry_ratio * left_span:
        return None

    # Rule 4 + 5: neckline projection and break confirmation.
    neck_break = _neckline(e1, e3, break_idx)
    break_price = close[break_idx]
    if not inverted and not (break_price < neck_break):
        return None
    if inverted and not (break_price > neck_break):
        return None

    neck_head = _neckline(e1, e3, e2[0])
    head_height = abs(e2[2] - neck_head)
    head_width = e3[0] - e1[0]
    slope = (e3[2] - e1[2]) / (e3[0] - e1[0]) if e3[0] != e1[0] else 0.0
    r2 = _pattern_r2(close, extrema)
    if inverted:
        target = neck_break + head_height
        stop = e4[2]
        side = "BULLISH"
    else:
        target = neck_break - head_height
        stop = e4[2]
        side = "BEARISH"

    return {
        "inverted": inverted,
        "side": side,
        "indices": {"E0": e0[0], "E1": e1[0], "E2": e2[0], "E3": e3[0], "E4": e4[0], "break": break_idx},
        "prices": {"E0": e0[2], "E1": e1[2], "E2": e2[2], "E3": e3[2], "E4": e4[2], "break": break_price},
        "neck_slope": slope,
        "neckline_at_break": neck_break,
        "head_height": head_height,
        "head_width": head_width,
        "pattern_r2": r2,
        "entry_price": break_price,
        "stop_price": stop,
        "target_price": target,
    }


def _scan_latest(close: list[float], order: int, symmetry_ratio: float, use_balance: bool, log_prices: bool) -> dict | None:
    work = _series(close, log_prices)
    pivots = _find_pivots(work, order)
    if len(pivots) < 5:
        return None
    latest_idx = len(work) - 1
    best: dict | None = None
    for i in range(len(pivots) - 4):
        extrema = pivots[i : i + 5]
        types = [p[1] for p in extrema]
        if extrema[-1][0] >= latest_idx:
            continue
        if types == [1, -1, 1, -1, 1]:
            pat = _validate(extrema, work, latest_idx, inverted=False, symmetry_ratio=symmetry_ratio, use_balance=use_balance)
        elif types == [-1, 1, -1, 1, -1]:
            pat = _validate(extrema, work, latest_idx, inverted=True, symmetry_ratio=symmetry_ratio, use_balance=use_balance)
        else:
            pat = None
        if pat is not None:
            best = pat
    if best is not None:
        best["pivots_detected"] = len(pivots)
    return best


def cc008_signal(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Detect a confirmed H&S/IHS neckline break on the latest bar."""
    enrich_data = enrich_data or {}
    close = extract_ohlcv(price_data)["close"]
    order = int(enrich_data.get("cc008_order", 6))
    symmetry_ratio = float(enrich_data.get("cc008_symmetry_ratio", 2.5))
    use_balance = bool(enrich_data.get("cc008_use_balance", True))
    log_prices = bool(enrich_data.get("cc008_log_prices", True))
    if len(close) < max(20, order * 4 + 5):
        return None

    pattern = _scan_latest(close, order, symmetry_ratio, use_balance, log_prices)
    if pattern is None:
        return None

    direction = "LONG" if pattern["inverted"] else "SHORT"
    r2 = pattern.get("pattern_r2")
    height_score = min(3.0, 100.0 * pattern["head_height"] / max(abs(pattern["entry_price"]), 1e-12))
    conviction = clamp_conviction(5.0 + height_score + (2.0 * r2 if isinstance(r2, float) else 0.0))

    return {
        "signal": "CC008_HEAD_AND_SHOULDERS",
        "direction": direction,
        "conviction": conviction,
        "reason": (
            f"Confirmed {'inverted ' if pattern['inverted'] else ''}Head & Shoulders neckline break; "
            f"head_height={pattern['head_height']:.4f}, target={pattern['target_price']:.4f}."
        ),
        "cc_ref": "CC-008",
        "metadata": {
            "ticker": ticker,
            **pattern,
            "order": order,
            "symmetry_ratio": symmetry_ratio,
            "use_balance": use_balance,
            "log_prices": log_prices,
            "validation_status": "OBSERVED_REFERENCE_ONLY",
            "formula": "5 alternating extrema + head dominance + balance + symmetry + neckline break",
        },
    }


register_signal(
    "CC-008",
    "Head & Shoulders Pattern Recognition",
    "Deterministic geometric H&S/IHS detector with neckline break confirmation.",
    "CANDIDATE GENERATOR / ENTRY TIMING",
    cc008_signal,
)
