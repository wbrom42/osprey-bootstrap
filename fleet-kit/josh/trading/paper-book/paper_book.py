"""
D-013 Layer 4: Paper Book — Virtual Position Tracking

Sits between SIZE and ACT in the pipeline. When a signal source is HOT
(≥65% calibration accuracy), the thesis gets a virtual position tracked
through to horizon close.

No money. No execution. Just measurement.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


PAPER_BOOK_DIR = Path("/home/infinitespark2/spark-vault/projects/D-013/build/paper-book")
OPEN_POSITIONS_FILE = PAPER_BOOK_DIR / "open_positions.json"
CLOSED_POSITIONS_FILE = PAPER_BOOK_DIR / "closed_positions.json"
PAPER_LEDGER_FILE = PAPER_BOOK_DIR / "paper_ledger.json"


def ensure_dirs():
    PAPER_BOOK_DIR.mkdir(parents=True, exist_ok=True)


def load_open():
    if OPEN_POSITIONS_FILE.exists():
        return json.loads(OPEN_POSITIONS_FILE.read_text())
    return {"positions": [], "updated_at": None}


def save_open(data: dict):
    ensure_dirs()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    OPEN_POSITIONS_FILE.write_text(json.dumps(data, indent=2, default=str))


def load_closed():
    if CLOSED_POSITIONS_FILE.exists():
        return json.loads(CLOSED_POSITIONS_FILE.read_text())
    return {"positions": [], "total_pnl": 0.0, "total_closed": 0}


def save_closed(data: dict):
    ensure_dirs()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    CLOSED_POSITIONS_FILE.write_text(json.dumps(data, indent=2, default=str))


def load_ledger():
    if PAPER_LEDGER_FILE.exists():
        return json.loads(PAPER_LEDGER_FILE.read_text())
    return {"starting_capital": 100000.0, "current_equity": 100000.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0, "total_trades": 0, "winning_trades": 0, "losing_trades": 0, "history": []}


def save_ledger(data: dict):
    ensure_dirs()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    PAPER_LEDGER_FILE.write_text(json.dumps(data, indent=2, default=str))


def open_paper_position(thesis: dict, current_price: float) -> dict | None:
    """
    Open a virtual paper position for a thesis from a HOT signal source.
    
    Returns position record or None if signal source doesn't qualify.
    """
    source = thesis.get("signal_source", "unknown")
    scores = _load_scores()
    src_score = scores.get("sources", {}).get(source, {})
    status = src_score.get("status", "COLD")
    
    # Only promote from HOT sources (≥65% accuracy)
    if status != "HOT":
        return None
    
    # Try Alpaca paper bridge first, fall back to local tracking
    try:
        from alpaca_bridge import open_paper_position as alpaca_open
        result = alpaca_open(thesis, current_price)
        if result and result.get("verdict") == "ALPACA_PAPER":
            return result
    except Exception:
        pass  # Fall through to local tracking
    
    position_size = _calculate_size(thesis, current_price)
    if position_size <= 0:
        return None
    
    position_id = f"PAPER-{thesis.get('pipeline_id', thesis.get('thesis_id', 'UNKNOWN'))}"
    direction = thesis.get("direction", "LONG").upper()
    horizon = thesis.get("time_horizon_days", 30)
    
    pos = {
        "position_id": position_id,
        "ticker": thesis.get("ticker", ""),
        "direction": direction,
        "entry_price": current_price,
        "entry_date": datetime.now(timezone.utc).isoformat(),
        "horizon_date": _horizon_date(horizon),
        "size_shares": position_size,
        "notional": round(position_size * current_price, 2),
        "signal_source": source,
        "thesis_summary": thesis.get("thesis_summary", "")[:200],
        "conviction": thesis.get("conviction", 0),
        "stop_loss_pct": 15.0,  # 15% stop
        "take_profit_pct": _take_profit_from_conviction(thesis.get("conviction", 5)),
        "status": "OPEN",
        "updates": []
    }
    
    open_book = load_open()
    open_book["positions"].append(pos)
    save_open(open_book)
    
    return pos


def close_paper_position(position_id: str, exit_price: float, reason: str = "CLOSED") -> dict | None:
    """Close a virtual paper position."""
    open_book = load_open()
    
    pos = None
    for i, p in enumerate(open_book["positions"]):
        if p["position_id"] == position_id:
            pos = open_book["positions"].pop(i)
            break
    
    if not pos:
        return None
    
    save_open(open_book)
    
    # Calculate P&L
    entry = pos["entry_price"]
    size = pos["size_shares"]
    direction = pos["direction"]
    
    if direction == "SHORT":
        pnl = (entry - exit_price) * size
        pnl_pct = ((entry - exit_price) / entry) * 100 if entry > 0 else 0
    else:
        pnl = (exit_price - entry) * size
        pnl_pct = ((exit_price - entry) / entry) * 100 if entry > 0 else 0
    
    pos["exit_price"] = exit_price
    pos["exit_date"] = datetime.now(timezone.utc).isoformat()
    pos["pnl"] = round(pnl, 2)
    pos["pnl_pct"] = round(pnl_pct, 2)
    pos["exit_reason"] = reason
    pos["status"] = "CLOSED"
    pos["won"] = pnl > 0
    
    closed_book = load_closed()
    closed_book["positions"].append(pos)
    closed_book["total_pnl"] = round(closed_book["total_pnl"] + pnl, 2)
    closed_book["total_closed"] += 1
    save_closed(closed_book)
    
    # Update ledger
    ledger = load_ledger()
    ledger["realized_pnl"] = round(ledger["realized_pnl"] + pnl, 2)
    ledger["current_equity"] = round(ledger["current_equity"] + pnl, 2)
    ledger["total_trades"] += 1
    if pnl > 0:
        ledger["winning_trades"] += 1
    else:
        ledger["losing_trades"] += 1
    ledger["history"].append({
        "date": datetime.now(timezone.utc).isoformat(),
        "position_id": position_id,
        "ticker": pos["ticker"],
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "equity": ledger["current_equity"]
    })
    save_ledger(ledger)
    
    return pos


def mark_to_market(prices: dict[str, float]) -> dict:
    """Update unrealized P&L for all open positions."""
    open_book = load_open()
    total_unrealized = 0.0
    triggered_stops = []
    triggered_targets = []
    
    for pos in open_book["positions"]:
        ticker = pos["ticker"]
        current = prices.get(ticker)
        if not current:
            continue
        
        entry = pos["entry_price"]
        direction = pos["direction"]
        
        if direction == "SHORT":
            unrealized = (entry - current) * pos["size_shares"]
            pnl_pct = ((entry - current) / entry) * 100
        else:
            unrealized = (current - entry) * pos["size_shares"]
            pnl_pct = ((current - entry) / entry) * 100
        
        pos["unrealized_pnl"] = round(unrealized, 2)
        pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
        pos["current_price"] = current
        pos["last_mtm"] = datetime.now(timezone.utc).isoformat()
        
        total_unrealized += unrealized
        
        # Check stops
        if pnl_pct <= -pos["stop_loss_pct"]:
            triggered_stops.append(pos["position_id"])
        elif pnl_pct >= pos["take_profit_pct"]:
            triggered_targets.append(pos["position_id"])
    
    save_open(open_book)
    
    ledger = load_ledger()
    ledger["unrealized_pnl"] = round(total_unrealized, 2)
    ledger["current_equity"] = round(100000.0 + ledger["realized_pnl"] + total_unrealized, 2)
    save_ledger(ledger)
    
    return {
        "unrealized_pnl": round(total_unrealized, 2),
        "equity": ledger["current_equity"],
        "stop_loss_triggers": triggered_stops,
        "take_profit_triggers": triggered_targets,
        "open_count": len(open_book["positions"])
    }


def close_expired() -> list[dict]:
    """Close positions that have passed their horizon date."""
    now = datetime.now(timezone.utc).isoformat()
    open_book = load_open()
    
    expired = [p for p in open_book["positions"] if p.get("horizon_date", "9999") <= now]
    results = []
    
    for pos in expired:
        # Default to entry price if we can't get current price
        exit_px = pos.get("current_price", pos["entry_price"])
        result = close_paper_position(pos["position_id"], exit_px, "HORIZON_EXPIRED")
        if result:
            results.append(result)
    
    return results


def get_paper_summary() -> dict:
    """Get paper trading summary statistics."""
    ledger = load_ledger()
    closed = load_closed()
    open_book = load_open()
    
    total = max(ledger["total_trades"], 1)
    win_rate = round(ledger["winning_trades"] / total * 100, 1) if total > 0 else 0
    
    # Source-level paper performance
    source_perf = {}
    for pos in closed["positions"]:
        src = pos.get("signal_source", "unknown")
        if src not in source_perf:
            source_perf[src] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        source_perf[src]["trades"] += 1
        if pos.get("won", False):
            source_perf[src]["wins"] += 1
        source_perf[src]["total_pnl"] = round(source_perf[src]["total_pnl"] + pos.get("pnl", 0), 2)
    
    return {
        "starting_capital": ledger["starting_capital"],
        "current_equity": round(ledger["current_equity"], 2),
        "realized_pnl": round(ledger["realized_pnl"], 2),
        "unrealized_pnl": round(ledger.get("unrealized_pnl", 0), 2),
        "total_return_pct": round((ledger["current_equity"] - ledger["starting_capital"]) / ledger["starting_capital"] * 100, 2),
        "total_trades": ledger["total_trades"],
        "winning_trades": ledger["winning_trades"],
        "losing_trades": ledger["losing_trades"],
        "win_rate": win_rate,
        "open_positions": len(open_book["positions"]),
        "closed_positions": closed["total_closed"],
        "source_performance": source_perf
    }


def _calculate_size(thesis: dict, price: float) -> float:
    """Calculate virtual position size based on conviction and risk."""
    conviction = thesis.get("conviction", 5)
    risk_per_trade = 0.02  # 2% of capital per trade
    capital = load_ledger()["current_equity"]
    risk_amount = capital * risk_per_trade * (conviction / 5)  # Scale by conviction
    if price > 0:
        return round(risk_amount / (price * 0.15), 0)  # 15% stop distance
    return 0


def _horizon_date(days: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _take_profit_from_conviction(conviction: float) -> float:
    """Map conviction to take-profit percentage."""
    if conviction <= 3:
        return 5.0
    elif conviction <= 5:
        return 10.0
    elif conviction <= 7:
        return 20.0
    elif conviction <= 9:
        return 30.0
    else:
        return 40.0


def _load_scores() -> dict:
    score_path = Path("/home/infinitespark2/spark-vault/projects/D-013/build/calibration/scores.json")
    if score_path.exists():
        return json.loads(score_path.read_text())
    return {"sources": {}}


# ---- CLI ----
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    
    if cmd == "summary":
        s = get_paper_summary()
        print(json.dumps(s, indent=2, default=str))
    elif cmd == "open":
        print(json.dumps(load_open(), indent=2, default=str))
    elif cmd == "closed":
        print(json.dumps(load_closed(), indent=2, default=str))
    elif cmd == "ledger":
        print(json.dumps(load_ledger(), indent=2, default=str))
    elif cmd == "mtm" and len(sys.argv) > 2:
        prices = json.loads(sys.argv[2])
        result = mark_to_market(prices)
        print(json.dumps(result, indent=2))
    elif cmd == "expire":
        results = close_expired()
        print(f"Closed {len(results)} expired positions")
        for r in results:
            print(f"  {r['position_id']}: {r['ticker']} P&L {r['pnl']} ({r['pnl_pct']}%)")
    else:
        print("Usage: paper_book.py [summary|open|closed|ledger|mtm|expire]")
