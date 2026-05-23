"""
D-013 Layer 3: Calibration Runner — Auto-verify and score

Runs after the daily thesis pipeline. Takes the digest output, checks
predictions against current prices, updates the score tracker, and
flags dead signals back into the screener.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path.home() / "spark-vault" / "projects" / "D-013"
sys.path.insert(0, str(PROJECT_ROOT / "build" / "calibration"))

from verify_engine import verify_thesis, verify_batch
from score_tracker import ScoreTracker


def run_calibration(digest_path: Path = None):
    """
    Run the full calibration loop after a thesis pipeline digest.
    
    1. Load digest entries
    2. Verify each thesis against current prices
    3. Record results in score tracker
    4. Apply feedback weights
    5. Output health report
    """
    # Find latest digest
    if digest_path is None:
        digest_dir = PROJECT_ROOT / "digest"
        digests = sorted(digest_dir.glob("d013-digest-*.json"), reverse=True)
        if not digests:
            return {"status": "NO_DATA", "message": "No digest files found"}
        digest_path = digests[0]
    
    with open(digest_path) as f:
        digest = json.load(f)
    
    entries = digest.get("entries", [])
    if not entries:
        return {"status": "NO_ENTRIES", "message": "Digest has no thesis entries"}
    
    # Load price data from enrichment cache
    price_lookup = _load_prices(entries)
    
    # Verify all entries
    verifications = []
    for entry in entries:
        ticker = entry.get("ticker", "")
        current_price = price_lookup.get(ticker)
        if current_price is None:
            continue
        
        thesis = {
            "ticker": ticker,
            "direction": entry.get("direction", "LONG"),
            "conviction": entry.get("judge_conviction", 5),
            "time_horizon_days": entry.get("time_horizon", 30),
            "signal_source": entry.get("signal_source", "UW_EQUITY"),
            "pipeline_id": entry.get("pipeline_id", ""),
            "price_at_thesis": entry.get("entry_price", current_price),
        }
        
        verification = verify_thesis(thesis, current_price)
        verification["ticker"] = ticker
        verification["thesis_id"] = entry.get("pipeline_id", "")
        verifications.append(verification)
    
    if not verifications:
        return {"status": "NO_PRICES", "message": "No price data available for verification"}
    
    # Record and score
    tracker = ScoreTracker()
    tracker.record_batch(verifications)
    
    # Get health report
    health = tracker.get_health_report()
    
    # Get feedback weights
    weights = tracker.apply_feedback()
    
    # Flag dead signals
    dead = tracker.flag_dead_signals()
    
    result = {
        "status": "OK",
        "run_id": f"cal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "digest": str(digest_path),
        "verified": len(verifications),
        "hits": sum(1 for v in verifications if v.get("hit")),
        "accuracy": round(sum(1 for v in verifications if v.get("hit")) / len(verifications) * 100, 1),
        "health_report": health,
        "feedback_weights": weights,
        "dead_signals": dead,
        "recommendation": _generate_recommendation(health)
    }
    
    # Save calibration output
    cal_dir = PROJECT_ROOT / "build" / "calibration" / "runs"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_path = cal_dir / f"calibration-{result['run_id']}.json"
    with open(cal_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    return result


def _load_prices(entries: list[dict]) -> dict[str, float]:
    """Load current prices from screener output and enrichment cache."""
    price_lookup = {}
    enrichment_dir = Path.home() / "spark-vault" / "cache" / "enrichment"
    screener_dir = Path.home() / "spark-vault" / "cache" / "d013-pipeline-runs"
    
    tickers = {e.get("ticker", "") for e in entries if e.get("ticker")}
    
    # First check screener output (has last_price from UW API)
    for run_dir in sorted(screener_dir.glob("d013-digest-*"), reverse=True):
        for ticker_file in run_dir.glob("*.json"):
            ticker_name = ticker_file.stem
            if ticker_name in tickers and ticker_name not in price_lookup:
                try:
                    data = json.loads(ticker_file.read_text())
                    price = data.get("price") or data.get("last_price") or data.get("close")
                    if price:
                        price_lookup[ticker_name] = float(price)
                except (json.JSONDecodeError, OSError, ValueError):
                    continue
    
    # Fallback: check enrichment cache for any price fields
    for ticker in tickers:
        if ticker not in price_lookup:
            cache_file = enrichment_dir / f"{ticker}.json"
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    price = data.get("last_price") or data.get("close_price") or data.get("price")
                    if price:
                        price_lookup[ticker] = float(price)
                except (json.JSONDecodeError, OSError, ValueError):
                    continue
    
    return price_lookup


def _generate_recommendation(health: dict) -> str:
    """Generate human-readable recommendation from health report."""
    dead = [s for s in health["sources"] if s["status"] == "DEAD" and s["verified"] >= 10]
    cold = [s for s in health["sources"] if s["status"] == "COLD" and s["verified"] >= 5]
    hot = [s for s in health["sources"] if s["status"] == "HOT"]
    
    parts = []
    if dead:
        parts.append(f"🚫 GATE OUT {len(dead)} dead signal(s): {', '.join(s['source'] for s in dead)}")
    if cold:
        parts.append(f"⬇️ REDUCE {len(cold)} cold signal(s) to 50% conviction weight")
    if hot:
        parts.append(f"🔥 BOOST {len(hot)} hot signal(s): {', '.join(s['source'] for s in hot)}")
    if not health["sources"]:
        parts.append("Insufficient data — no recommendations yet")
    
    return " | ".join(parts) if parts else "All signals within normal range"


if __name__ == "__main__":
    digest_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result = run_calibration(digest_arg)
    print(json.dumps(result, indent=2, default=str))
