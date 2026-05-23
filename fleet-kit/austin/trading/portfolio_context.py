"""
D-013-005: Portfolio Context — Holdings / Risk Scan Inputs

Provides portfolio context for the sizing engine and veto rules.
Aggregates position data from enrichment cache and portfolio snapshots.

Context includes:
- Holdings snapshot (positions across accounts)
- Sector exposure breakdown
- Cash available
- Correlation matrix (top holdings)
- Drawdown metrics
- Volatility (VIX proxy)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


# ── Default Portfolio Context ────────────────────────────────────────────

DEFAULT_HOLDINGS = {
    "AAPL": {"shares": 10, "avg_price": 175.0, "sector": "Technology"},
    "MSFT": {"shares": 5, "avg_price": 380.0, "sector": "Technology"},
    "SPY": {"shares": 20, "avg_price": 480.0, "sector": "ETF"},
    "TLT": {"shares": 15, "avg_price": 95.0, "sector": "Fixed Income"},
}

DEFAULT_HOLDING_VALUES = {
    t: h["shares"] * h["avg_price"]
    for t, h in DEFAULT_HOLDINGS.items()
}
DEFAULT_TOTAL_VALUE = sum(DEFAULT_HOLDING_VALUES.values()) + 50_000  # + cash


# ── Enrichment Cache Reader ──────────────────────────────────────────────

ENRICHMENT_CACHE_DIR = Path.home() / "spark-vault" / "cache" / "enrichment"


def load_enrichment(ticker: str) -> dict | None:
    """Load enrichment data for a ticker from the cache.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Enrichment data dict, or None if not found
    """
    ticker = ticker.upper()
    path = ENRICHMENT_CACHE_DIR / f"{ticker}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def list_enrichment_tickers() -> list[str]:
    """List all tickers with enrichment data available."""
    if not ENRICHMENT_CACHE_DIR.exists():
        return []
    return sorted(
        f.stem for f in ENRICHMENT_CACHE_DIR.iterdir()
        if f.suffix == ".json"
    )


# ── Portfolio Context Builder ────────────────────────────────────────────

class PortfolioContext:
    """Build and manage portfolio context for thesis evaluation."""

    def __init__(
        self,
        holdings: dict[str, dict] | None = None,
        cash_available: float | None = None,
        total_value: float | None = None,
        current_drawdown: float = 0.0,
        vix: float | None = None,
    ):
        self.holdings = holdings or {}
        self.cash_available = cash_available or 0.0
        self.total_value = total_value or 0.0
        self.current_drawdown = current_drawdown
        self.vix = vix
        self._correlations: dict[str, float] = {}
        self._sector_exposure: dict[str, float] = {}

        if self.holdings:
            self._build()

    def _build(self):
        """Build internal state from holdings."""
        if not self.total_value and self.holdings:
            # Estimate from holdings + cash
            positions_value = sum(
                h.get("shares", 0) * h.get("avg_price", 0)
                for h in self.holdings.values()
            )
            self.total_value = positions_value + self.cash_available

        if not self.cash_available and self.total_value:
            positions_value = sum(
                h.get("shares", 0) * h.get("avg_price", 0)
                for h in self.holdings.values()
            )
            self.cash_available = max(0, self.total_value - positions_value)

        # Build sector exposure
        sector_values: dict[str, float] = {}
        for ticker, h in self.holdings.items():
            value = h.get("shares", 0) * h.get("avg_price", 0)
            sector = h.get("sector", "Other")
            sector_values[sector] = sector_values.get(sector, 0) + value

        self._sector_exposure = {
            s: v / self.total_value if self.total_value > 0 else 0
            for s, v in sector_values.items()
        }

        # Build placeholder correlations (in production, load from enrichment)
        tickers = list(self.holdings.keys())
        for i, t1 in enumerate(tickers):
            for t2 in tickers[i + 1:]:
                corr_key = f"{t1}_{t2}" if t1 < t2 else f"{t2}_{t1}"
                # Conservative default — moderate correlation
                self._correlations[corr_key] = 0.5

    def to_dict(self) -> dict:
        """Serialize to dict for pipeline use."""
        return {
            "holdings": {
                t: {"sector": h.get("sector", "Other"), "value": h.get("shares", 0) * h.get("avg_price", 0)}
                for t, h in self.holdings.items()
            },
            "cash_available": self.cash_available,
            "total_value": self.total_value,
            "current_drawdown": self.current_drawdown,
            "vix": self.vix,
            "num_positions": len(self.holdings),
            "sector_exposure": self._sector_exposure,
            "correlations": self._correlations,
        }

    @classmethod
    def from_default(cls) -> PortfolioContext:
        """Create a default portfolio context for testing."""
        return cls(
            holdings=DEFAULT_HOLDINGS,
            cash_available=50_000,
            total_value=DEFAULT_TOTAL_VALUE,
            current_drawdown=0.02,
            vix=16.5,
        )

    @classmethod
    def from_file(cls, path: str) -> PortfolioContext:
        """Load portfolio context from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            holdings=data.get("holdings"),
            cash_available=data.get("cash_available"),
            total_value=data.get("total_value"),
            current_drawdown=data.get("current_drawdown", 0.0),
            vix=data.get("vix"),
        )


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="D-013 Portfolio Context Builder")
    parser.add_argument("--output", default="portfolio_context.json", help="Output path")
    parser.add_argument("--default", action="store_true", help="Use default portfolio")
    parser.add_argument("--list-tickers", action="store_true", help="List enrichment cache tickers")
    parser.add_argument("--ticker", help="Load enrichment data for a specific ticker")
    args = parser.parse_args()

    if args.list_tickers:
        tickers = list_enrichment_tickers()
        print(f"Enrichment cache ({len(tickers)} tickers):")
        for t in tickers:
            print(f"  {t}")
        sys.exit(0)

    if args.ticker:
        data = load_enrichment(args.ticker)
        if data:
            print(json.dumps(data, indent=2))
        else:
            print(f"No enrichment data for {args.ticker}")
        sys.exit(0)

    if args.default:
        ctx = PortfolioContext.from_default()
    else:
        ctx = PortfolioContext.from_default()  # Default for now

    output = ctx.to_dict()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"✅ Portfolio context written: {output_path}")
    print(f"   Holdings: {len(ctx.holdings)} positions")
    print(f"   Total value: ${ctx.total_value:,.0f}")
    print(f"   Cash: ${ctx.cash_available:,.0f}")
    print(f"   Drawdown: {ctx.current_drawdown:.1%}")
    print(f"   VIX: {ctx.vix or 'N/A'}")


if __name__ == "__main__":
    main()
