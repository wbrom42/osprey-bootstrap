"""CC-005 — Time Series Reversibility / Irreversibility regime wrapper.

Implements the math contract's primary permutation-pattern Jensen-Shannon
Divergence method directly on log returns. This is a regime/context signal, not
a standalone trade authorization.
"""

from __future__ import annotations

from collections import Counter
from itertools import permutations
from math import log
import random
from typing import Any

from signals import register_signal
from signals._utils import clamp_conviction, direction_from_int, extract_ohlcv


DEFAULT_WINDOW = 100
DEFAULT_ORDER = 4
DEFAULT_DELAY = 1
DEFAULT_SURROGATES = 200
DEFAULT_ALPHA = 0.95


def _log_returns(close: list[float]) -> list[float]:
    returns: list[float] = []
    for prev, cur in zip(close, close[1:]):
        if prev > 0 and cur > 0:
            returns.append(log(cur / prev))
    return returns


def _ordinal_distribution(series: list[float], order: int, delay: int) -> dict[tuple[int, ...], float]:
    n_patterns = len(series) - (order - 1) * delay
    patterns = list(permutations(range(order)))
    counts: Counter[tuple[int, ...]] = Counter({p: 0 for p in patterns})
    if n_patterns <= 0:
        return {p: 0.0 for p in patterns}

    for start in range(n_patterns):
        subseq = [series[start + j * delay] for j in range(order)]
        # Stable ranking handles ties by preserving first occurrence order.
        pattern = tuple(sorted(range(order), key=lambda j: (subseq[j], j)))
        counts[pattern] += 1

    total = float(n_patterns)
    return {p: counts[p] / total for p in patterns}


def _entropy(probabilities: list[float]) -> float:
    return -sum(p * log(p, 2) for p in probabilities if p > 0)


def _jsd_base2(p: dict[tuple[int, ...], float], q: dict[tuple[int, ...], float]) -> float:
    keys = sorted(set(p) | set(q))
    pv = [p.get(k, 0.0) for k in keys]
    qv = [q.get(k, 0.0) for k in keys]
    m = [(a + b) / 2.0 for a, b in zip(pv, qv)]
    # Contract §3: JSD(P||Q)=H(M)-0.5H(P)-0.5H(Q), base-2, range [0,1].
    return max(0.0, min(1.0, _entropy(m) - 0.5 * _entropy(pv) - 0.5 * _entropy(qv)))


def _perm_reversibility(series: list[float], order: int, delay: int) -> float:
    p_fwd = _ordinal_distribution(series, order, delay)
    p_rev = _ordinal_distribution(list(reversed(series)), order, delay)
    return _jsd_base2(p_fwd, p_rev)


def _bootstrap_threshold(
    series: list[float], order: int, delay: int, surrogates: int, alpha: float, seed: int
) -> float:
    rng = random.Random(seed)
    scores: list[float] = []
    for _ in range(surrogates):
        shuffled = list(series)
        rng.shuffle(shuffled)
        scores.append(_perm_reversibility(shuffled, order, delay))
    if not scores:
        return 1.0
    scores.sort()
    idx = min(len(scores) - 1, max(0, int(round(alpha * (len(scores) - 1)))))
    return scores[idx]


def cc005_reversibility(
    ticker: str,
    enrich_data: dict[str, Any] | None = None,
    price_data: Any = None,
) -> dict | None:
    """Return the latest reversibility regime using CC-005's JSD formula."""
    enrich_data = enrich_data or {}
    ohlcv = extract_ohlcv(price_data)
    close = ohlcv["close"]
    returns = _log_returns(close)

    window = int(enrich_data.get("cc005_window", DEFAULT_WINDOW))
    order = int(enrich_data.get("cc005_order", DEFAULT_ORDER))
    delay = int(enrich_data.get("cc005_delay", DEFAULT_DELAY))
    surrogates = int(enrich_data.get("cc005_surrogates", DEFAULT_SURROGATES))
    alpha = float(enrich_data.get("cc005_alpha", DEFAULT_ALPHA))

    min_required = window + (order - 1) * delay
    if len(returns) < min_required or order < 2 or delay < 1:
        return None

    chunk = returns[-window:]
    jsd = _perm_reversibility(chunk, order, delay)
    seed = sum((i + 1) * ord(ch) for i, ch in enumerate(ticker)) % (2**32)
    threshold = _bootstrap_threshold(chunk, order, delay, surrogates, alpha, seed=seed)
    is_irreversible = jsd > threshold

    recent_drift = sum(chunk) / max(1, len(chunk))
    direction = direction_from_int(1 if recent_drift > 0 else -1 if recent_drift < 0 else 0) if is_irreversible else "NEUTRAL"
    regime = "irreversible" if is_irreversible else "reversible"
    ratio = jsd / threshold if threshold > 0 else 0.0
    conviction = clamp_conviction(3.0 + 4.0 * min(1.5, ratio) + (1.0 if is_irreversible else 0.0))

    return {
        "signal": "CC005_REVERSIBILITY_REGIME",
        "direction": direction,
        "conviction": conviction,
        "reason": (
            f"Permutation-pattern JSD={jsd:.4f} vs bootstrap threshold={threshold:.4f}; "
            f"regime={regime}. Regime/context only, not standalone trade authority."
        ),
        "cc_ref": "CC-005",
        "metadata": {
            "ticker": ticker,
            "jsd": jsd,
            "threshold": threshold,
            "is_irreversible": is_irreversible,
            "regime": regime,
            "recent_log_return_drift": recent_drift,
            "window": window,
            "embedding_order": order,
            "delay": delay,
            "surrogates": surrogates,
            "alpha": alpha,
            "method": "permutation_pattern_jsd_base2",
            "validation_status": "NEEDS_REVIEW",
        },
    }


register_signal(
    "CC-005",
    "Time Series Reversibility",
    "Permutation-pattern Jensen-Shannon divergence regime detector.",
    "REGIME DETECTION / STRATEGY FILTER",
    cc005_reversibility,
)
