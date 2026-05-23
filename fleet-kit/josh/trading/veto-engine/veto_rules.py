"""
D-013-002: VetoEngine Rules — Rule-Based Triggers

Rule-based triggers for each VetoEngine power level (APPROVE/REDUCE/DELAY/REJECT).

Each rule is a VetoRule subclass with an evaluate() method that returns
a trigger dict or None. These rules are evaluated by the VetoEngine
in order. The first hard rule (REJECT) wins, then DELAY, then REDUCE.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from veto_engine import VetoRule, PowerLevel


# ── Rejection Rules (REJECT) ─────────────────────────────────────────────

class TickerBlacklistRule(VetoRule):
    """Reject theses on blacklisted tickers (excluded securities)."""

    def __init__(self, blacklist: list[str] | None = None):
        super().__init__(
            name="ticker_blacklist",
            description="Reject theses on blacklisted tickers",
        )
        self.blacklist = set(t.upper() for t in (blacklist or []))

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        ticker = thesis.get("ticker", "").upper()
        if ticker in self.blacklist:
            return {
                "level": "REJECT",
                "reason": f"Ticker {ticker} is on the blacklist",
                "rule_name": self.name,
            }
        return None


class DirectionMismatchRule(VetoRule):
    """Reject if thesis direction conflicts with a fundamental constraint."""

    def __init__(self):
        super().__init__(
            name="direction_mismatch",
            description="Reject if thesis direction conflicts with constraints",
        )

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        direction = thesis.get("direction", "").upper()
        ticker = thesis.get("ticker", "").upper()

        # Example: reject SHORT on tickers not eligible for shorting
        if direction == "SHORT":
            # Placeholder — could check short interest availability
            pass

        return None


class ConvictionFloorRule(VetoRule):
    """Reject if thesis conviction is below the absolute minimum threshold."""

    def __init__(self, min_conviction: float = 3.0):
        super().__init__(
            name="conviction_floor",
            description=f"Reject thesis with conviction below {min_conviction}/10",
        )
        self.min_conviction = min_conviction

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        conviction = thesis.get("conviction", 0)
        if isinstance(conviction, (int, float)) and conviction < self.min_conviction:
            return {
                "level": "REJECT",
                "reason": f"Conviction {conviction}/10 below minimum threshold {self.min_conviction}/10",
                "rule_name": self.name,
            }
        return None


class TimeHorizonMismatchRule(VetoRule):
    """Reject if time horizon is incompatible with the trading mandate."""

    # Valid horizons for D-013 (no day trading)
    VALID_HORIZONS = {"SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"}

    def __init__(self):
        super().__init__(
            name="time_horizon_mismatch",
            description="Reject intraday time horizons (no day trading)",
        )

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        horizon = thesis.get("time_horizon", "").upper()
        if horizon == "INTRADAY" or "INTRADAY" in horizon:
            return {
                "level": "REJECT",
                "reason": f"Time horizon '{horizon}' is not permitted (no day trading)",
                "rule_name": self.name,
            }
        return None


# ── Delay Rules (DELAY) ──────────────────────────────────────────────────

class VolatilityDelayRule(VetoRule):
    """Delay thesis if market volatility exceeds threshold."""

    def __init__(self, vix_threshold: float = 30.0, delay_hours: int = 48):
        super().__init__(
            name="volatility_delay",
            description=f"Delay thesis if VIX > {vix_threshold}",
        )
        self.vix_threshold = vix_threshold
        self.delay_hours = delay_hours

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        if portfolio_context:
            vix = portfolio_context.get("vix")
            if vix and isinstance(vix, (int, float)) and vix > self.vix_threshold:
                return {
                    "level": "DELAY",
                    "reason": f"VIX {vix} exceeds threshold {self.vix_threshold}, delaying thesis",
                    "rule_name": self.name,
                    "delay_hours": self.delay_hours,
                }
        return None


class EarningsBlackoutRule(VetoRule):
    """Delay thesis entering within 48h of earnings."""

    def __init__(self, blackout_hours: int = 48):
        super().__init__(
            name="earnings_blackout",
            description="Delay thesis within earnings blackout window",
        )
        self.blackout_hours = blackout_hours

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        earnings_dte = thesis.get("earnings_dte")
        if earnings_dte is not None:
            try:
                dte = int(earnings_dte)
                if 0 < dte <= 2:  # Within 48h of earnings
                    return {
                        "level": "DELAY",
                        "reason": f"Earnings in {dte} days — within {self.blackout_hours}h blackout window",
                        "rule_name": self.name,
                        "delay_hours": (dte + 1) * 24,  # Delay past earnings
                    }
            except (ValueError, TypeError):
                pass
        return None


class VolumeConfirmationDelay(VetoRule):
    """Delay if volume confirmation is needed before acting."""

    def __init__(self, min_daily_volume: int = 500_000, delay_hours: int = 24):
        super().__init__(
            name="volume_confirmation_delay",
            description="Delay if volume data is insufficient",
        )
        self.min_daily_volume = min_daily_volume
        self.delay_hours = delay_hours

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        avg_volume = thesis.get("avg_volume")
        if avg_volume is not None:
            try:
                if int(avg_volume) < self.min_daily_volume:
                    return {
                        "level": "DELAY",
                        "reason": f"Avg volume {avg_volume} below {self.min_daily_volume} minimum — delaying for confirmation",
                        "rule_name": self.name,
                        "delay_hours": self.delay_hours,
                    }
            except (ValueError, TypeError):
                pass
        return None


# ── Reduction Rules (REDUCE) ─────────────────────────────────────────────

class SectorConcentrationRule(VetoRule):
    """Reduce position sizing if sector is already overweight."""

    def __init__(self, max_sector_exposure: float = 0.25, reduction_factor: float = 0.5):
        super().__init__(
            name="sector_concentration",
            description=f"Reduce if sector exposure exceeds {max_sector_exposure:.0%}",
        )
        self.max_sector_exposure = max_sector_exposure
        self.reduction_factor = reduction_factor

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        if not portfolio_context:
            return None

        sector = thesis.get("sector", thesis.get("ticker", "UNKNOWN"))
        sector_exposure = portfolio_context.get("sector_exposure", {})

        current = sector_exposure.get(sector, 0.0)
        if current > self.max_sector_exposure:
            return {
                "level": "REDUCE",
                "reason": f"Sector {sector} at {current:.1%} exceeds {self.max_sector_exposure:.0%} max",
                "rule_name": self.name,
                "reduction_factor": self.reduction_factor,
            }
        return None


class PortfolioDrawdownRule(VetoRule):
    """Reduce if portfolio is in a drawdown exceeding threshold."""

    def __init__(self, drawdown_threshold: float = 0.05, reduction_factor: float = 0.5):
        super().__init__(
            name="portfolio_drawdown",
            description=f"Reduce if portfolio drawdown exceeds {drawdown_threshold:.0%}",
        )
        self.drawdown_threshold = drawdown_threshold
        self.reduction_factor = reduction_factor

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        if not portfolio_context:
            return None

        current_drawdown = portfolio_context.get("current_drawdown", 0.0)
        if current_drawdown > self.drawdown_threshold:
            return {
                "level": "REDUCE",
                "reason": f"Portfolio drawdown {current_drawdown:.1%} exceeds {self.drawdown_threshold:.0%}",
                "rule_name": self.name,
                "reduction_factor": self.reduction_factor,
            }
        return None


class CorrelationWarningRule(VetoRule):
    """Reduce if thesis ticker is highly correlated with existing positions."""

    def __init__(self, correlation_threshold: float = 0.8, reduction_factor: float = 0.7):
        super().__init__(
            name="correlation_warning",
            description=f"Reduce if correlation with existing positions > {correlation_threshold}",
        )
        self.correlation_threshold = correlation_threshold
        self.reduction_factor = reduction_factor

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        if not portfolio_context:
            return None

        correlations = portfolio_context.get("correlations", {})
        ticker = thesis.get("ticker", "").upper()
        existing = portfolio_context.get("holdings", {})

        high_corr = []
        for holding in existing:
            corr_key = f"{ticker}_{holding}" if ticker < holding else f"{holding}_{ticker}"
            corr_val = correlations.get(corr_key, 0.0)
            if corr_val > self.correlation_threshold:
                high_corr.append((holding, corr_val))

        if high_corr:
            high_str = ", ".join(f"{h}={c:.2f}" for h, c in high_corr)
            return {
                "level": "REDUCE",
                "reason": f"Ticker {ticker} highly correlated with: {high_str}",
                "rule_name": self.name,
                "reduction_factor": self.reduction_factor,
            }
        return None


class ConvictionReductionRule(VetoRule):
    """Gradually reduce sizing as conviction decreases (separate from floor)."""

    def __init__(self):
        super().__init__(
            name="conviction_based_reduction",
            description="Reduce sizing proportionally to conviction level",
        )

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        # Handled by VetoEngine core's _evaluate_conviction_reduction
        return None


# ── Default Ruleset ──────────────────────────────────────────────────────

DEFAULT_RULES: list[VetoRule] = [
    # REJECT rules (hard stops, evaluated first)
    TickerBlacklistRule(),
    ConvictionFloorRule(min_conviction=3.0),
    TimeHorizonMismatchRule(),

    # DELAY rules (temporal holds)
    VolatilityDelayRule(),
    EarningsBlackoutRule(),
    VolumeConfirmationDelay(),

    # REDUCE rules (scaling adjustments)
    SectorConcentrationRule(),
    PortfolioDrawdownRule(),
    CorrelationWarningRule(),
]
