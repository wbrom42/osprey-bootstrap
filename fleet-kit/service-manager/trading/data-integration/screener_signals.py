"""D-013: Screener Signals — Auto-Identify Thesis Candidates from Enrichment Cache

Reads the UW enrichment cache and applies quantitative screens to surface
high-signal thesis candidates. Each candidate includes a ticker, direction,
conviction score, and contextual enrichment data.

Signal Screens:
  - EARNS: Earnings-driven plays (earnings_dte 7-45, IV rank > 50)
  - INSIDER: Insider conviction (buys > sells, positive seasonality)
  - ANALYST: Analyst-driven (high analyst activity, positive bias)
  - MOMENTUM: Strong volume + implied move + volume ratio

Usage:
    python3 screener_signals.py                          # Full scan, print candidates
    python3 screener_signals.py --output candidates.json  # Save to file
    python3 screener_signals.py --min-conviction 6        # Only high-conviction picks
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ENRICHMENT_DIR = Path.home() / "spark-vault" / "cache" / "enrichment"
NEUROTRADER_DIR = Path.home() / "spark-vault" / "projects" / "D-013" / "build" / "signals"
GMGN_CACHE_DIR = Path.home() / "spark-vault" / "finance-claw-archive" / "cache" / "gmgn"
GAUNTLET_DIR = Path.home() / "spark-vault" / "projects" / "gauntlet"
GAUNTLET_CANDIDATES_DIR = GAUNTLET_DIR / "candidates"
GAUNTLET_REPORTS_DIR = GAUNTLET_DIR / "reports"
GAUNTLET_POSTMORTEMS_DIR = GAUNTLET_DIR / "postmortems"


# ── Signal Rules ──────────────────────────────────────────────────────────

def signal_earnings(rec: dict) -> dict | None:
    """Earnings-driven plays: upcoming earnings + elevated IV."""
    dte = rec.get("earnings_dte")
    iv = rec.get("iv_rank", 0)
    if dte is not None and 7 <= dte <= 45 and iv >= 50:
        conviction = min(10.0, 5.0 + (iv - 50) / 10 + max(0, (30 - abs(dte - 20)) / 5))
        return {
            "signal": "EARNS",
            "direction": "LONG",
            "conviction": round(conviction, 1),
            "reason": f"Earnings in {dte}d, IV rank {iv}",
        }
    return None


def signal_insider(rec: dict) -> dict | None:
    """Insider conviction: buys significantly outpace sells."""
    buys = rec.get("insider_buys_30d", 0)
    sells = rec.get("insider_sells_30d", 0)
    seasonality = rec.get("seasonality_positive_pct", 50)
    if buys > sells * 2 and buys >= 2 and seasonality > 52:
        conviction = min(10.0, 5.0 + min(buys, 10) + (seasonality - 50) / 5)
        return {
            "signal": "INSIDER",
            "direction": "LONG" if buys > sells else "SHORT",
            "conviction": round(conviction, 1),
            "reason": f"Buy:{buys} Sell:{sells} ratio, {seasonality}% seasonal positive",
        }
    return None


def signal_analyst(rec: dict) -> dict | None:
    """Analyst-driven: high recent analyst activity + favorable patterns."""
    actions = rec.get("analyst_actions_30d", 0)
    seasonality = rec.get("seasonality_positive_pct", 50)
    if actions >= 8 and seasonality > 55:
        conviction = min(10.0, 5.0 + min(actions - 8, 10) / 2 + (seasonality - 55) / 10)
        return {
            "signal": "ANALYST",
            "direction": "LONG",
            "conviction": round(conviction, 1),
            "reason": f"{actions} analyst actions in 30d, {seasonality}% seasonal positive",
        }
    return None


def signal_momentum(rec: dict) -> dict | None:
    """Momentum: strong volume + elevated implied move + volume profile."""
    imp_move = rec.get("implied_move_30d", 0)
    call_7d = rec.get("call_vol_avg_7d", 0)
    put_7d = rec.get("put_vol_avg_7d", 0)
    call_30d = rec.get("call_vol_avg_30d", 0)
    put_30d = rec.get("put_vol_avg_30d", 0)

    # Volume growth signal (7d avg vs 30d avg)
    total_7d = call_7d + put_7d
    total_30d = call_30d + put_30d
    vol_growth = (total_7d / total_30d - 1) if total_30d > 0 else 0

    if imp_move >= 3.5 and vol_growth > 0.15:
        # Determine direction from put/call ratio trend
        ratio_7d = put_7d / call_7d if call_7d > 0 else 999
        ratio_30d = put_30d / call_30d if call_30d > 0 else 999
        direction = "SHORT" if ratio_7d > ratio_30d * 1.2 else "LONG"

        conviction = min(10.0, 5.0 + min(imp_move, 10) / 2 + min(vol_growth * 100, 10))
        return {
            "signal": "MOMENTUM",
            "direction": direction,
            "conviction": round(conviction, 1),
            "reason": f"Implied move {imp_move}%, vol growth {vol_growth:.0%}",
        }
    return None


def signal_neurotrader(rec: dict) -> dict | None:
    """NeuroTrader math contract signals — runs the active signal registry.

    Loads and evaluates registered CC-XXX signal wrappers against enrichment
    data. Returns the highest-conviction signal result.
    """
    import importlib

    if not NEUROTRADER_DIR.exists():
        return None

    try:
        sys.path.insert(0, str(NEUROTRADER_DIR.parent))
        from signals import get_active_signals, register_signal  # noqa: F811

        active = get_active_signals()
        if not active:
            return None

        best: dict | None = None
        for sig in active:
            try:
                result = sig["fn"](rec.get("ticker", "?"), enrich_data=rec)
                if result is None:
                    continue
                result["cc_ref"] = sig["cc"]
                if best is None or result.get("conviction", 0) > best.get("conviction", 0):
                    best = result
            except Exception:
                continue

        if best:
            return {
                "signal": f"NT_{best.get('cc_ref', 'CC')}",
                "direction": best.get("direction", "NEUTRAL"),
                "conviction": min(10.0, best.get("conviction", 0)),
                "reason": best.get("reason", "NeuroTrader signal"),
            }
    except Exception:
        pass
    return None


def signal_gmgn(rec: dict) -> dict | None:
    """GMGN on-chain signal — reads GMGN cache for token signals.

    Checks the GMGN daily snapshot for ticker matches. Returns signal if
    on-chain volume/activity crosses threshold.
    """
    ticker = rec.get("ticker", "").lower()
    if not ticker or not GMGN_CACHE_DIR.exists():
        return None

    # Check daily trending snapshots
    daily_dir = GMGN_CACHE_DIR / "daily"
    if not daily_dir.exists():
        return None

    snapshots = sorted(daily_dir.glob("trending_*.json"))
    if not snapshots:
        return None

    latest = snapshots[-1]
    try:
        data = json.loads(latest.read_text())
        # Handle {code, data: {rank: [...]}} structure
        tokens = []
        if isinstance(data, dict):
            d = data.get("data", data)
            tokens = d.get("rank", d.get("tokens", d.get("items", [])))
        elif isinstance(data, list):
            tokens = data

        for token in tokens:
            symbol = token.get("symbol", token.get("token", "")).lower()
            name = token.get("name", "").lower()
            # Match ticker against symbol or name
            if ticker in symbol or symbol in ticker or ticker in name:
                vol_24h = token.get("volume_24h", 0) or token.get("volume", 0)
                price_change = token.get("price_change_percent", 0) or token.get("price_change_24h", 0) or 0

                if vol_24h > 100000:
                    direction = "LONG" if price_change > 0 else "SHORT"
                    conviction = min(10.0, 5.0 + min(abs(price_change), 20) / 4)
                    return {
                        "signal": "GMGN",
                        "direction": direction,
                        "conviction": round(conviction, 1),
                        "reason": f"{symbol.upper()} 24h vol ${vol_24h:,.0f}, change {price_change:+.1f}%",
                    }
    except Exception:
        pass
    return None


def signal_gauntlet(rec: dict) -> dict | None:
    """Gauntlet CLEAR candidates — D-016 survivors that feed into D-013 thesis pipeline.

    Reads the D-016 Gauntlet tracker to find candidates that have survived
    falsifier checkpoints. Handles multiple tracker format versions.
    A candidate is CLEAR if:
    - ACTIVE/alive in the gauntlet tracker
    - No postmortem filed
    - Has passed at least the 1d forward observation window
    """
    from datetime import datetime, timezone

    ticker = rec.get("ticker", "").upper()
    if not ticker:
        return None

    if not GAUNTLET_DIR.exists() or not GAUNTLET_CANDIDATES_DIR.exists():
        return None

    # Find matching gauntlet candidate for this ticker
    candidate_files = sorted(GAUNTLET_CANDIDATES_DIR.glob(f"PPG-*-{ticker}-*.md"))
    if not candidate_files:
        return None

    ppg_id = f"PPG-{candidate_files[0].stem.split('-')[1]}"  # e.g., PPG-001

    # Check if killed via postmortem (primary kill indicator)
    postmortems = sorted(GAUNTLET_POSTMORTEMS_DIR.glob(f"{ppg_id}-{ticker}*"))
    if postmortems:
        return None  # Candidate was killed

    # Read candidate card for thesis context
    try:
        card_text = candidate_files[0].read_text()
    except OSError:
        return None

    # Check the gauntlet tracker (latest report)
    reports = sorted(GAUNTLET_REPORTS_DIR.glob("gauntlet-tracker-*.json"))
    if not reports:
        return None

    tracker = json.loads(reports[-1].read_text())

    # Find the tracker entry (try both key formats: PPG-NNN-TICKER and PPG-NNN)
    tracker_entry = None
    for cid, entry in tracker.get("candidates", {}).items():
        if entry.get("ticker", "").upper() == ticker:
            tracker_entry = entry
            break

    if not tracker_entry:
        return None

    # Check alive status (handle both formats)
    alive = tracker_entry.get("alive")
    status = tracker_entry.get("status")
    falsifier_triggered = tracker_entry.get("falsifier_triggered", False)
    falsifier_status = tracker_entry.get("falsifier_status", "")

    # Determine if candidate is alive
    if alive is not None:
        # New format (May 19+): alive boolean
        if not alive:
            return None
    elif status is not None:
        # Old format (May 14-18): status string
        if status != "ACTIVE":
            return None
    else:
        # Can't determine, be safe and reject
        return None

    # Also check falsifier_triggered for new format
    if falsifier_triggered:
        return None

    # Compute days since observation
    obs_date_str = tracker_entry.get("obs_date", "")
    if not obs_date_str:
        # Fallback: try to extract obs_date from candidate card header
        for line in card_text.split("\n"):
            if "Observation Date" in line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    obs_date_str = parts[2].strip()
                    break

    if not obs_date_str:
        return None  # Can't compute window without observation date

    try:
        obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_since_obs = (datetime.now(timezone.utc) - obs_date).days
    except (ValueError, TypeError):
        return None

    # Must have passed at least the 1d forward window
    if days_since_obs < 1:
        return None

    # Calculate conviction based on checkpoint survival + buffer
    conviction = 5.0  # Base
    if days_since_obs >= 1:
        conviction += 1.0
    if days_since_obs >= 5:
        conviction += 1.0
    if days_since_obs >= 20:
        conviction += 1.5
    if days_since_obs >= 60:
        conviction += 2.0

    # Buffer bonus for new format
    buffer_pct = tracker_entry.get("buffer_pct")
    if buffer_pct is not None and buffer_pct > 0:
        conviction += min(2.0, buffer_pct / 10.0)  # +1 per 10% buffer, max +2

    conviction = min(10.0, round(conviction, 1))

    # Extract sector and thesis from card
    sector = "N/A"
    thesis_snippet = "Gauntlet survivor"
    for line in card_text.split("\n"):
        line_lower = line.lower()
        if "sector" in line_lower and "**" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                sector = parts[2].strip()
                thesis_snippet = sector
        if "bull thesis" in line_lower:
            parts = line.split("|")
            if len(parts) >= 3:
                thesis_snippet = parts[2].strip()[:120]

    falsifier = tracker_entry.get("falsifier_floor", 0)
    checkpoints = sum([days_since_obs >= 1, days_since_obs >= 5,
                       days_since_obs >= 20, days_since_obs >= 60])
    reason = (
        f"GAUNTLET {ppg_id} ({ticker}): {days_since_obs}d survivor, "
        f"falsifier=${falsifier}, checkpoints={checkpoints}/4, "
        f"thesis: {thesis_snippet}"
    )[:200]

    return {
        "signal": "GAUNTLET",
        "direction": "LONG",  # All gauntlet picks are positive (LONG) theses
        "conviction": conviction,
        "reason": reason,
        "enrich_data": {
            "ppg_id": ppg_id,
            "sector": sector,
            "days_since_obs": days_since_obs,
            "falsifier_floor": falsifier,
            "checkpoints_passed": checkpoints,
            "buffer_pct": buffer_pct,
            "observed_close": tracker_entry.get("obs_close", 0),
        },
    }


def _alive_status(entry: dict) -> bool:
    """Check if a tracker entry indicates an alive/active candidate.
    Handles both old format (status: ACTIVE) and new format (alive: True)."""
    alive = entry.get("alive")
    if alive is not None:
        return bool(alive)
    status = entry.get("status")
    if status is not None:
        return status == "ACTIVE"
    # Default: suspect dead if we can't determine
    return False


def _get_obs_date(entry: dict, card_text: str = "") -> str | None:
    """Get observation date from tracker entry, with fallback to candidate card."""
    obs_date = entry.get("obs_date")
    if obs_date:
        return str(obs_date)
    # Try card text
    for line in card_text.split("\n"):
        if "Observation Date" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                return parts[2].strip()
    return None


def get_gauntlet_only_candidates(min_conviction: float = 0) -> list[dict]:
    """Return GAUNTLET CLEAR candidates whose tickers are NOT in the enrichment cache.

    This catches gauntlet survivors that the standard enrichment-cache scan
    would miss because no UW enrichment data exists for that ticker yet.
    """
    from datetime import datetime, timezone

    if not GAUNTLET_DIR.exists() or not GAUNTLET_CANDIDATES_DIR.exists():
        return []

    # Get the set of tickers already in enrichment cache
    enrichment_tickers = {p.stem.upper() for p in ENRICHMENT_DIR.glob("*.json")}
    if not enrichment_tickers:
        return []

    # Read the latest tracker
    reports = sorted(GAUNTLET_REPORTS_DIR.glob("gauntlet-tracker-*.json"))
    if not reports:
        return []
    try:
        tracker = json.loads(reports[-1].read_text())
    except (OSError, json.JSONDecodeError):
        return []

    tracker_entries = tracker.get("candidates", {})

    # Read all gauntlet candidate cards
    now = datetime.now(timezone.utc)
    candidates = []
    for card_path in sorted(GAUNTLET_CANDIDATES_DIR.glob("*.md")):
        parts = card_path.stem.split("-")
        # Format: PPG-NNN-TICKER-v0.1.md
        if len(parts) >= 4:
            ticker = parts[2].upper()
        else:
            continue

        # Skip if already in enrichment cache
        if ticker in enrichment_tickers:
            continue

        ppg_id = f"{parts[0]}-{parts[1]}"  # e.g., PPG-001

        # Check if killed via postmortem
        postmortems = list(GAUNTLET_POSTMORTEMS_DIR.glob(f"{ppg_id}-{ticker}*"))
        if postmortems:
            continue

        # Read card text for fallback
        card_text = ""
        try:
            card_text = card_path.read_text()
        except OSError:
            pass

        # Find tracker entry
        tracker_entry = None
        for cid, entry in tracker_entries.items():
            if entry.get("ticker", "").upper() == ticker:
                tracker_entry = entry
                break

        if not tracker_entry:
            continue

        # Must be alive
        if not _alive_status(tracker_entry):
            continue

        # Check falsifier_triggered
        if tracker_entry.get("falsifier_triggered", False):
            continue

        # Get obs_date
        obs_date_str = _get_obs_date(tracker_entry, card_text)
        if not obs_date_str:
            continue

        try:
            obs_date = datetime.strptime(str(obs_date_str).strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_since_obs = (now - obs_date).days
        except (ValueError, TypeError):
            continue

        if days_since_obs < 1:
            continue

        # Calculate conviction
        conviction = 5.0
        if days_since_obs >= 1:
            conviction += 1.0
        if days_since_obs >= 5:
            conviction += 1.0
        if days_since_obs >= 20:
            conviction += 1.5
        if days_since_obs >= 60:
            conviction += 2.0

        # Buffer bonus
        buffer_pct = tracker_entry.get("buffer_pct")
        if buffer_pct is not None and buffer_pct > 0:
            conviction += min(2.0, buffer_pct / 10.0)

        conviction = min(10.0, round(conviction, 1))

        if conviction < min_conviction:
            continue

        falsifier_floor = tracker_entry.get("falsifier_floor", 0)
        checkpoints = sum([days_since_obs >= 1, days_since_obs >= 5,
                           days_since_obs >= 20, days_since_obs >= 60])

        # Extract thesis from card
        thesis_snippet = "Gauntlet survivor"
        for line in card_text.split("\n"):
            if "bull thesis" in line.lower():
                parts_line = line.split("|")
                if len(parts_line) >= 3:
                    thesis_snippet = parts_line[2].strip()[:120]
                    break

        candidates.append({
            "ticker": ticker,
            "direction": "LONG",
            "signal": "GAUNTLET",
            "conviction": conviction,
            "reason": (
                f"GAUNTLET {ppg_id} ({ticker}): {days_since_obs}d survivor, "
                f"falsifier=${falsifier_floor}, checkpoints={checkpoints}/4, "
                f"thesis: {thesis_snippet}"
            )[:200],
            "enrich_data": {
                "ppg_id": ppg_id,
                "days_since_obs": days_since_obs,
                "falsifier_floor": falsifier_floor,
                "checkpoints_passed": checkpoints,
                "buffer_pct": buffer_pct,
                "observed_close": tracker_entry.get("obs_close", 0),
            },
        })

    candidates.sort(key=lambda c: c["conviction"], reverse=True)
    return candidates


# ── Scanner ───────────────────────────────────────────────────────────────

ALL_SIGNALS = [signal_earnings, signal_insider, signal_analyst, signal_momentum, signal_neurotrader, signal_gmgn, signal_gauntlet]


def scan_enrichment(min_conviction: float = 0) -> list[dict]:
    """Scan all enrichment files and return thesis candidates, including gauntlet CLEAR survivors."""
    candidates = []

    if not ENRICHMENT_DIR.exists():
        print(f"WARNING: Enrichment cache not found at {ENRICHMENT_DIR}")
        return candidates

    for path in sorted(ENRICHMENT_DIR.glob("*.json")):
        ticker = path.stem.upper()
        try:
            rec = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️  {ticker}: failed to parse ({e})")
            continue

        best: dict | None = None
        for signal_fn in ALL_SIGNALS:
            result = signal_fn(rec)
            if result is None:
                continue
            if best is None or result["conviction"] > best["conviction"]:
                best = result

        if best and best["conviction"] >= min_conviction:
            candidates.append({
                "ticker": ticker,
                "direction": best["direction"],
                "signal": best["signal"],
                "conviction": best["conviction"],
                "reason": best["reason"],
                "enrich_data": {
                    k: rec.get(k)
                    for k in [
                        "iv_rank", "implied_move_30d", "earnings_dte",
                        "analyst_actions_30d", "insider_buys_30d",
                        "insider_sells_30d", "seasonality_positive_pct",
                        "call_vol_avg_7d", "put_vol_avg_7d",
                        "generated_at",
                    ]
                },
            })

    # Merge gauntlet-only candidates (tickers not in enrichment cache)
    gauntlet_only = get_gauntlet_only_candidates(min_conviction=min_conviction)
    existing_tickers = {c["ticker"] for c in candidates}
    for gc in gauntlet_only:
        if gc["ticker"] not in existing_tickers:
            candidates.append(gc)

    # Sort by conviction descending
    candidates.sort(key=lambda c: c["conviction"], reverse=True)
    return candidates


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="D-013 Screener Signals")
    parser.add_argument("--output", help="Save candidates to JSON file")
    parser.add_argument("--min-conviction", type=float, default=0,
                        help="Minimum conviction threshold (default: 0 = all)")
    parser.add_argument("--summary", action="store_true",
                        help="Print summary only")
    parser.add_argument("--gauntlet", action="store_true",
                        help="Show gauntlet CLEAR candidates only (standalone)")
    args = parser.parse_args()

    if args.gauntlet:
        # Standalone gauntlet CLEAR report — shows all CLEAR gauntlet candidates
        all_candidates = []
        seen_tickers = set()

        # 1) Enrichment-cache gauntlet candidates
        for path in sorted(ENRICHMENT_DIR.glob("*.json")):
            ticker = path.stem.upper()
            try:
                rec = json.loads(path.read_text())
                rec["ticker"] = ticker
                result = signal_gauntlet(rec)
                if result and result["conviction"] >= args.min_conviction:
                    all_candidates.append({
                        "ticker": ticker,
                        "direction": result["direction"],
                        "signal": result["signal"],
                        "conviction": result["conviction"],
                        "reason": result["reason"],
                        "enrich_data": result.get("enrich_data", {}),
                    })
                    seen_tickers.add(ticker)
            except Exception:
                pass

        # 2) Gauntlet-only candidates (tickers not in enrichment cache)
        for gc in get_gauntlet_only_candidates(min_conviction=args.min_conviction):
            if gc["ticker"] not in seen_tickers:
                all_candidates.append(gc)

        all_candidates.sort(key=lambda c: c["conviction"], reverse=True)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(all_candidates, indent=2))
            print(f"Saved {len(all_candidates)} gauntlet CLEAR candidates to {out_path}")

        if not all_candidates:
            print("No CLEAR gauntlet candidates found.")
        else:
            print(f"\n🛡️  GAUNTLET CLEAR candidates — {len(all_candidates)} candidate(s)\n")
            for c in all_candidates:
                check = c.get("enrich_data", {}).get("checkpoints_passed", "?")
                print(f"  {c['ticker']:6s}  GAUNTLET  conviction={c['conviction']}/10  "
                      f"checkpoints={check}/4  {c['reason'][:100]}")
        return 0

    candidates = scan_enrichment(min_conviction=args.min_conviction)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(candidates, indent=2))
        print(f"Saved {len(candidates)} candidates to {out_path}")

    if args.summary and candidates:
        print(f"\n📊 D-013 Screener — {len(candidates)} candidate(s)\n")
        for c in candidates:
            print(f"  {c['ticker']:6s}  {c['direction']:6s}  {c['signal']:8s}  "
                  f"conviction={c['conviction']}/10  {c['reason']}")
    elif not args.output and not args.summary:
        print(json.dumps(candidates, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
