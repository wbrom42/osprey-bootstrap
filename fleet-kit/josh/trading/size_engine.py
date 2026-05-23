"""
D-013-005: Position Sizing Engine

Determines position size for a thesis based on:
- Conviction score (from JUDGE and VetoEngine)
- Portfolio context (current holdings, risk budget)
- Concentration limits per sector/position
- Account type and capital constraints

Sizing is always fractional — outputs a recommended allocation as
a percentage of portfolio and a unit count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ── Sizing Constants ─────────────────────────────────────────────────────

DEFAULT_MAX_POSITION_PCT = 0.10  # Max 10% of portfolio in single position
DEFAULT_MAX_SECTOR_PCT = 0.25    # Max 25% of portfolio in single sector
DEFAULT_MAX_TOTAL_POSITIONS = 20  # Max 20 positions total
DEFAULT_RISK_PER_TRADE_PCT = 0.02  # Max 2% portfolio risk per trade
DEFAULT_CASH_RESERVE_PCT = 0.15    # Keep 15% cash reserve

CONVICTION_SIZING_TABLE = {
    # conviction_score -> (base_pct, risk_multiplier)
    (1, 3):   (0.01, 0.25),   # Very low conviction: 1% position, 0.25x risk
    (3, 5):   (0.03, 0.50),   # Low conviction: 3% position, 0.5x risk
    (5, 7):   (0.05, 1.00),   # Moderate conviction: 5% position, 1x risk
    (7, 9):   (0.08, 1.50),   # High conviction: 8% position, 1.5x risk
    (9, 10):  (0.10, 2.00),   # Very high conviction: 10% position, 2x risk
}


# ── Size Engine ─────────────────────────────────────────────────────────

class SizeEngine:
    """Position sizing engine for the thesis pipeline.

    Takes a thesis + portfolio context and produces a recommended
    position size, respecting portfolio constraints.
    """

    def __init__(
        self,
        max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
        max_sector_pct: float = DEFAULT_MAX_SECTOR_PCT,
        max_total_positions: int = DEFAULT_MAX_TOTAL_POSITIONS,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
        cash_reserve_pct: float = DEFAULT_CASH_RESERVE_PCT,
    ):
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_total_positions = max_total_positions
        self.risk_per_trade_pct = risk_per_trade_pct
        self.cash_reserve_pct = cash_reserve_pct

    def size_position(
        self,
        thesis: dict,
        portfolio: dict | None = None,
        veto_result: dict | None = None,
    ) -> dict:
        """Determine recommended position size for a thesis.

        Args:
            thesis: Thesis dict (must have conviction, direction, etc.)
            portfolio: Portfolio context dict with holdings, total_value, etc.
            veto_result: Optional VetoEngine result with reduction_factor

        Returns:
            Size decision dict with recommended size, allocation %, and constraints
        """
        # Get the effective conviction score
        conviction = self._get_conviction(thesis, portfolio, veto_result)

        # Look up base sizing table
        base_pct, risk_mult = self._lookup_conviction_sizing(conviction)

        # Apply VetoEngine reduction
        if veto_result:
            reduction = veto_result.get("reduction_factor", 1.0)
            if reduction is not None and reduction < 1.0:
                base_pct *= reduction

        # Portfolio-aware sizing
        if portfolio:
            base_pct = self._apply_portfolio_constraints(base_pct, thesis, portfolio)
            base_pct = self._apply_concentration_limits(base_pct, thesis, portfolio)
            base_pct = self._apply_cash_reserve(base_pct, portfolio)

        # Calculate absolute position size
        total_value = portfolio.get("total_value", 100_000) if portfolio else 100_000
        cash_available = portfolio.get("cash_available", total_value) if portfolio else total_value

        recommended_pct = min(base_pct, self.max_position_pct)
        recommended_value = total_value * recommended_pct
        recommended_value = min(recommended_value, cash_available)

        # Calculate unit count based on entry price
        entry_price = thesis.get("entry_price") or 100
        if entry_price <= 0:
            entry_price = 100  # fallback default
        unit_count = int(recommended_value / entry_price)

        # Risk-budget check
        risk_amount = recommended_value * risk_mult * self.risk_per_trade_pct
        risk_budget_ok = risk_amount <= (total_value * self.risk_per_trade_pct)

        return {
            "recommended_pct": round(recommended_pct, 4),
            "recommended_value": round(recommended_value, 2),
            "unit_count": unit_count,
            "entry_price": entry_price,
            "effective_conviction": conviction,
            "risk_amount": round(risk_amount, 2),
            "risk_budget_ok": risk_budget_ok,
            "constraints_applied": {
                "max_position_pct": self.max_position_pct,
                "max_sector_pct": self.max_sector_pct,
                "cash_available": cash_available,
                "total_value": total_value,
            },
            "veto_reduction": veto_result.get("reduction_factor", 1.0) if veto_result else 1.0,
        }

    def _get_conviction(
        self,
        thesis: dict,
        portfolio: dict | None = None,
        veto_result: dict | None = None,
    ) -> float:
        """Get the effective conviction score for sizing.

        Priority:
        1. VetoEngine override_conviction
        2. Judge verdict conviction_score
        3. Thesis conviction
        4. Default 5.0
        """
        if veto_result and veto_result.get("override_conviction") is not None:
            return float(veto_result["override_conviction"])

        if thesis.get("judge_verdict"):
            jv = thesis["judge_verdict"]
            if jv.get("conviction_score") is not None:
                return float(jv["conviction_score"])

        return float(thesis.get("conviction", 5.0))

    def _lookup_conviction_sizing(self, conviction: float) -> tuple[float, float]:
        """Look up base allocation % and risk multiplier for a conviction score."""
        for (low, high), (base, risk) in sorted(CONVICTION_SIZING_TABLE.items()):
            if low <= conviction < high:
                return base, risk
        # Fallback for edge values
        if conviction < 1:
            return 0.005, 0.1
        return 0.10, 2.0

    def _apply_portfolio_constraints(
        self, base_pct: float, thesis: dict, portfolio: dict
    ) -> float:
        """Apply portfolio-level constraints to position size."""
        holdings = portfolio.get("holdings", {})
        num_positions = len(holdings)

        # Limit if approaching max positions
        if num_positions >= self.max_total_positions:
            return min(base_pct, 0.02)  # Only allow small additions

        # Reduce if near max positions
        if num_positions >= self.max_total_positions * 0.8:
            base_pct *= (self.max_total_positions - num_positions) / (self.max_total_positions * 0.2)

        return base_pct

    def _apply_concentration_limits(
        self, base_pct: float, thesis: dict, portfolio: dict
    ) -> float:
        """Apply concentration limits per sector."""
        sector = thesis.get("sector", thesis.get("ticker", "UNKNOWN"))
        sector_exposure = portfolio.get("sector_exposure", {})
        current_sector_pct = sector_exposure.get(sector, 0.0)

        if current_sector_pct + base_pct > self.max_sector_pct:
            available = max(0, self.max_sector_pct - current_sector_pct)
            return min(base_pct, available)

        return base_pct

    def _apply_cash_reserve(self, base_pct: float, portfolio: dict) -> float:
        """Apply cash reserve constraint."""
        total_value = portfolio.get("total_value", 100_000)
        cash = portfolio.get("cash_available", total_value)
        target_cash = total_value * self.cash_reserve_pct
        surplus_cash = cash - target_cash

        if surplus_cash <= 0:
            return 0.0  # No cash available after reserve

        # Cash-constrained: reduce position size proportionally
        cash_pct = surplus_cash / total_value
        base_value = base_pct * total_value
        if base_value > surplus_cash:
            return surplus_cash / total_value

        return base_pct


# ── CLI ─────────────────────────────────────────────────────────────────

def _load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="D-013 Position Sizing Engine")
    parser.add_argument("--thesis", required=True, help="Thesis JSON file path")
    parser.add_argument("--portfolio", help="Portfolio context JSON file path")
    parser.add_argument("--veto", help="VetoEngine result JSON file path")
    parser.add_argument("--output", default="size_decision.json", help="Output path")
    args = parser.parse_args()

    thesis = _load_json(args.thesis)
    portfolio = _load_json(args.portfolio) if args.portfolio else None
    veto_result = _load_json(args.veto) if args.veto else None

    engine = SizeEngine()
    decision = engine.size_position(thesis, portfolio, veto_result)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(decision, f, indent=2, default=str)

    print(f"✅ Sizing complete")
    print(f"   Conviction: {decision['effective_conviction']}/10")
    print(f"   Allocation: {decision['recommended_pct']*100:.1f}% (${decision['recommended_value']:,.0f})")
    print(f"   Units: {decision['unit_count']} @ ${decision['entry_price']}")
    print(f"   Risk budget: {'OK' if decision['risk_budget_ok'] else 'OVER'}")
    print(f"   Veto reduction: {decision['veto_reduction']}x")
    print(f"   Output: {output_path}")


if __name__ == "__main__":
    main()
