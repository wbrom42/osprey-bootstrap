"""D-013: Signal Registry — NeuroTrader Math Contract Signal Types

Defines the canonical signal interface and registry for all 22 NeuroTrader
math contracts. Each signal is a callable that takes price/enrichment data
and returns a signal score dict.

Signal interface:
    signal_function(ticker: str, enrich_data: dict | None = None,
                    price_data: dict | None = None) -> SignalResult | None

SignalResult:
    {
        "signal": str,          # signal type name
        "direction": str,       # LONG | SHORT | NEUTRAL
        "conviction": float,    # 0-10
        "reason": str,          # human-readable explanation
        "cc_ref": str,          # CC-XXX reference
        "metadata": dict        # extra signal-specific data
    }
"""

from __future__ import annotations
import sys
from typing import Any, Callable

# Support signal modules that explicitly use `from .__init__ import register_signal`.
# Without this alias Python can load a second module object named
# `signals.__init__`, producing a separate SIGNAL_REGISTRY.
sys.modules.setdefault(f"{__name__}.__init__", sys.modules[__name__])

SignalFn = Callable[..., dict | None]

# ── Registry ─────────────────────────────────────────────────────────────

SIGNAL_REGISTRY: dict[str, dict] = {}

def register_signal(
    cc_id: str,
    name: str,
    description: str,
    lane: str,
    fn: SignalFn,
    active: bool = True,
):
    """Register a signal type by CC number."""
    SIGNAL_REGISTRY[cc_id] = {
        "cc": cc_id,
        "name": name,
        "description": description,
        "lane": lane,
        "fn": fn,
        "active": active,
    }


def get_active_signals() -> list[dict]:
    """Return all active signal registrations."""
    return [s for s in SIGNAL_REGISTRY.values() if s["active"]]


def get_signal(cc_id: str) -> dict | None:
    """Get a signal registration by CC ID."""
    return SIGNAL_REGISTRY.get(cc_id)


def list_signal_names() -> list[str]:
    """Return names of all registered signals."""
    return [s["name"] for s in SIGNAL_REGISTRY.values() if s["active"]]
