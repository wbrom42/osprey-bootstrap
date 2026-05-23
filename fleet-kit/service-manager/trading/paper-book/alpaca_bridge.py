"""
D-013 Alpaca Paper Bridge — Real Paper Trading via Alpaca API

Wires the PAPER step to Alpaca's paper trading endpoint.
HOT sources → real paper orders through Alpaca instead of local JSON tracking.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce


SECRETS_DIR = Path("/home/infinitespark2/.hermes/secrets")
PAPER_BOOK_DIR = Path("/home/infinitespark2/spark-vault/projects/D-013/build/paper-book")
ALPACA_STATE_FILE = PAPER_BOOK_DIR / "alpaca_state.json"


def _get_client() -> TradingClient:
    """Get Alpaca paper trading client from stored keys."""
    key_id = (SECRETS_DIR / "alpaca_key_id").read_text().strip()
    secret = (SECRETS_DIR / "alpaca_secret").read_text().strip()
    return TradingClient(key_id, secret, paper=True)


def load_state() -> dict:
    if ALPACA_STATE_FILE.exists():
        return json.loads(ALPACA_STATE_FILE.read_text())
    return {
        "active_positions": {},  # thesis_id → alpaca_order_id
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_realized_pnl": 0.0,
        "history": []
    }


def save_state(state: dict):
    PAPER_BOOK_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    ALPACA_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def open_paper_position(thesis: dict, current_price: float) -> dict | None:
    """
    Open an Alpaca paper position for a thesis from a HOT signal source.
    
    Returns position record or None if signal source doesn't qualify.
    """
    from pathlib import Path as _Path
    
    # Check signal source quality from calibration scores
    score_path = _Path("/home/infinitespark2/spark-vault/projects/D-013/build/calibration/scores.json")
    if not score_path.exists():
        return None
    
    scores = json.loads(score_path.read_text())
    source = thesis.get("signal_source", "unknown")
    src_score = scores.get("sources", {}).get(source, {})
    status = src_score.get("status", "COLD")
    
    if status != "HOT":
        return None
    
    try:
        client = _get_client()
    except Exception as e:
        return {"verdict": "ERROR", "error": f"Alpaca client init failed: {e}"}
    
    ticker = (thesis.get("ticker", "")).upper()
    direction = thesis.get("direction", "LONG").upper()
    conviction = thesis.get("conviction", 5)
    
    # Calculate position size using Alpaca buying power
    try:
        account = client.get_account()
        buying_power = float(account.buying_power)
    except Exception:
        buying_power = 50000.0
    
    # 2% risk per trade, scaled by conviction
    risk_amount = buying_power * 0.02 * (conviction / 5)
    qty = max(1, int(risk_amount / current_price)) if current_price > 0 else 1
    
    # Prevent tiny positions on expensive stocks
    if qty * current_price < 100:
        qty = max(1, int(100 / current_price))
    
    notional = round(qty * current_price, 2)
    if notional > buying_power * 0.10:  # Cap at 10% of BP
        qty = int((buying_power * 0.10) / current_price)
        notional = round(qty * current_price, 2)
    
    side = OrderSide.BUY if direction == "LONG" else OrderSide.SELL_SHORT
    
    try:
        # Market order for simplicity in paper
        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=side,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_request)
        
        position_id = f"ALPACA-{order.id}"
        
        state = load_state()
        state["active_positions"][position_id] = {
            "alpaca_order_id": str(order.id),
            "thesis_id": thesis.get("pipeline_id", thesis.get("thesis_id", "UNKNOWN")),
            "ticker": ticker,
            "direction": direction,
            "qty": qty,
            "entry_price": current_price,
            "notional": notional,
            "signal_source": source,
            "conviction": conviction,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "status": "FILLING"
        }
        save_state(state)
        
        return {
            "position_id": position_id,
            "ticker": ticker,
            "entry_price": current_price,
            "size_shares": qty,
            "notional": notional,
            "source": source,
            "alpaca_order_id": str(order.id),
            "verdict": "ALPACA_PAPER"
        }
    
    except Exception as e:
        return {"verdict": "ERROR", "error": f"Order failed: {e}"}


def get_account_summary() -> dict:
    """Get current Alpaca paper account summary."""
    try:
        client = _get_client()
        account = client.get_account()
        positions = client.get_all_positions()
        
        total_unrealized = sum(float(p.unrealized_pl or 0) for p in positions)
        
        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "equity": round(float(account.equity), 2),
            "buying_power": round(float(account.buying_power), 2),
            "cash": round(float(account.cash), 2),
            "portfolio_value": round(float(account.portfolio_value), 2),
            "unrealized_pl": round(total_unrealized, 2),
            "open_positions": len(positions),
            "paper": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


def close_position(position_id: str) -> dict | None:
    """Close a tracked Alpaca position."""
    client = _get_client()
    state = load_state()
    
    if position_id not in state["active_positions"]:
        return None
    
    pos = state["active_positions"][position_id]
    ticker = pos["ticker"]
    qty = pos["qty"]
    side = OrderSide.SELL if pos["direction"] == "LONG" else OrderSide.BUY
    
    try:
        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=side,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_request)
        
        # Record in history
        state["total_trades"] += 1
        state["history"].append({
            "position_id": position_id,
            "ticker": ticker,
            "action": "CLOSE",
            "alpaca_order_id": str(order.id),
            "closed_at": datetime.now(timezone.utc).isoformat()
        })
        del state["active_positions"][position_id]
        save_state(state)
        
        return {"position_id": position_id, "ticker": ticker, "order_id": str(order.id), "status": "CLOSING"}
    
    except Exception as e:
        return {"error": str(e)}


def close_all_d013_positions() -> int:
    """Close all D-013 tracked positions (not old crypto league positions)."""
    state = load_state()
    closed = 0
    for pid in list(state["active_positions"].keys()):
        result = close_position(pid)
        if result and "error" not in result:
            closed += 1
    return closed


def sync_positions_from_alpaca() -> dict:
    """Pull current Alpaca positions and cross-reference with D-013 tracker."""
    client = _get_client()
    state = load_state()
    
    alpaca_positions = client.get_all_positions()
    d013_tracked = {v["alpaca_order_id"]: k for k, v in state["active_positions"].items()}
    
    orphaned = []  # Alpaca positions NOT from D-013
    matched = []   # Alpaca positions that ARE from D-013
    stale = []     # D-013 tracked but not in Alpaca
    
    for pos in alpaca_positions:
        # Alpaca positions don't store our order_id directly
        # We track by position symbol
        pdata = {
            "symbol": pos.symbol,
            "qty": pos.qty,
            "entry_price": float(pos.avg_entry_price),
            "unrealized_pl": float(pos.unrealized_pl or 0),
            "market_value": float(pos.market_value or 0)
        }
        
        # Check if any D-013 position matches this symbol
        d013_match = None
        for pid, pstate in state["active_positions"].items():
            if pstate["ticker"] == pos.symbol:
                d013_match = pid
                break
        
        if d013_match:
            matched.append({**pdata, "d013_id": d013_match})
        else:
            orphaned.append(pdata)
    
    # Check for stale D-013 entries
    for pid, pstate in state["active_positions"].items():
        if not any(pos.symbol == pstate["ticker"] for pos in alpaca_positions):
            stale.append({"d013_id": pid, "ticker": pstate["ticker"]})
    
    return {
        "alphabet": len(alpaca_positions),
        "d013_tracked": len(state["active_positions"]),
        "d013_matched": matched,
        "orphaned": orphaned,
        "stale": stale,
        "total_orphaned": len(orphaned)
    }


# CLI
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    
    if cmd == "summary":
        s = get_account_summary()
        print(json.dumps(s, indent=2, default=str))
    elif cmd == "sync":
        s = sync_positions_from_alpaca()
        print(json.dumps(s, indent=2, default=str))
    elif cmd == "close_all":
        n = close_all_d013_positions()
        print(f"Closed {n} D-013 positions")
    elif cmd == "state":
        s = load_state()
        print(json.dumps(s, indent=2, default=str))
    else:
        print("Usage: alpaca_bridge.py [summary|sync|close_all|state]")
