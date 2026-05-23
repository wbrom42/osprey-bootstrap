"""D-013: Daily Runner — Auto-Thesis Pipeline

Orchestrates the full daily D-013 cycle:
  1. Screens enrichment cache for high-signal candidates
  2. Runs the thesis pipeline for top candidates
  3. Collects notable verdicts into a digest file
  4. Outputs to digest dir + prints summary to stdout

Usage:
    python3 daily_runner.py                              # Full run
    python3 daily_runner.py --max-candidates 10          # Override top-N limit
    python3 daily_runner.py --digest-dir ./digest         # Custom output dir
    python3 daily_runner.py --dry-run                     # Show what would run
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "spark-vault" / "projects" / "D-013"
PIPELINE = PROJECT_ROOT / "build" / "thesis-pipeline" / "pipeline.py"
SCREENER = PROJECT_ROOT / "build" / "data-integration" / "screener_signals.py"
DIGEST_DIR = PROJECT_ROOT / "digest"
DEFAULT_CACHE_DIR = Path.home() / "spark-vault" / "cache" / "enrichment"

# Calibration integration
CALIBRATION_DIR = PROJECT_ROOT / "build" / "calibration"

# Default: top 8 candidates per daily run (keeps pipeline execution manageable)
DEFAULT_MAX_CANDIDATES = 8

# Notable threshold: verdicts that should appear in the digest
NOTABLE_CONVICTION_MIN = 7.0  # conviction >= 7/10 to be "notable"
NOTABLE_VERDICTS = {"SUPPORT_THESIS"}  # verdict labels that count as notable


# ── Runner ────────────────────────────────────────────────────────────────

def get_candidates(max_candidates: int, min_conviction: float) -> list[dict]:
    """Run the screener and return sorted candidates."""
    result = subprocess.run(
        [sys.executable, str(SCREENER), "--min-conviction", str(min_conviction)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"⚠️  Screener failed (exit {result.returncode}): {result.stderr[:200]}")
        return []

    try:
        all_candidates = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"⚠️  Screener output not valid JSON, raw: {result.stdout[:200]}")
        return []

    return all_candidates[:max_candidates]


def run_pipeline(ticker: str, direction: str, output_path: Path) -> dict | None:
    """Run the thesis pipeline for a single candidate."""
    result = subprocess.run(
        [
            sys.executable, str(PIPELINE),
            "--ticker", ticker,
            "--direction", direction,
            "--output", str(output_path),
        ],
        capture_output=True, text=True, timeout=600,  # 10 min per pipeline run
    )

    pipeline_result: dict | None = None
    status = "COMPLETE" if result.returncode == 0 else "FAILED"

    # Try to read the pipeline output
    if output_path.exists():
        try:
            pipeline_result = json.loads(output_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if not pipeline_result:
        pipeline_result = {
            "status": status,
            "stderr": result.stderr[:500] if result.stderr else None,
            "stdout": result.stdout[:500] if result.stdout else None,
        }

    return pipeline_result


def is_notable(pipeline_result: dict) -> bool:
    """Check if a pipeline verdict is notable enough for the digest."""
    final = pipeline_result.get("final", {})
    stages = pipeline_result.get("stages", {})
    judge = stages.get("judge", {})

    verdict = judge.get("verdict", "")
    conviction = judge.get("conviction_score", 0)
    can_execute = final.get("can_execute", False)

    if verdict in NOTABLE_VERDICTS and conviction >= NOTABLE_CONVICTION_MIN:
        return True
    if can_execute:
        return True
    return False


def generate_digest(results: list[dict], run_id: str) -> dict:
    """Generate a structured digest from pipeline results."""
    entries = []
    notable_count = 0

    for r in results:
        ticker = r.get("ticker", "???")
        signal = r.get("signal", "?")
        direction = r.get("direction", "LONG")
        pipeline_result = r.get("pipeline_result", {})
        error = r.get("error")

        stages = pipeline_result.get("stages", {})
        judge = stages.get("judge", {})
        veto = stages.get("veto", {})
        act = stages.get("act", {})
        final = pipeline_result.get("final", {})

        entry = {
            "ticker": ticker,
            "direction": direction,
            "signal": signal,
            "screener_conviction": r.get("conviction"),
            "judge_verdict": judge.get("verdict", "N/A"),
            "judge_conviction": judge.get("conviction_score", 0),
            "veto_power_level": veto.get("power_level", "N/A"),
            "action": final.get("action", "N/A"),
            "can_execute": final.get("can_execute", False),
            "error": error,
        }
        entries.append(entry)

        if is_notable(pipeline_result):
            notable_count += 1

    digest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(results),
        "notable_count": notable_count,
        "entries": entries,
    }
    return digest


def write_digest(digest: dict, digest_dir: Path):
    """Write digest to disk."""
    digest_dir.mkdir(parents=True, exist_ok=True)
    run_id = digest["run_id"]
    path = digest_dir / f"{run_id}.json"
    path.write_text(json.dumps(digest, indent=2))
    return path


def clean_old_digests(digest_dir: Path, keep: int = 30):
    """Remove digests older than N days."""
    import time
    cutoff = time.time() - keep * 86400
    for p in sorted(digest_dir.glob("d013-digest-*.json")):
        if p.stat().st_mtime < cutoff:
            p.unlink()


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="D-013 Daily Runner")
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES,
                        help=f"Maximum candidates per run (default: {DEFAULT_MAX_CANDIDATES})")
    parser.add_argument("--min-conviction", type=float, default=6.0,
                        help="Minimum screener conviction (default: 6.0)")
    parser.add_argument("--digest-dir", type=str, default=str(DIGEST_DIR),
                        help="Output directory for digests")
    parser.add_argument("--dry-run", action="store_true",
                        help="Screen candidates but don't run pipeline")
    args = parser.parse_args()

    digest_dir = Path(args.digest_dir)
    run_id = f"d013-digest-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    output_dir = Path.home() / "spark-vault" / "cache" / "d013-pipeline-runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"  D-013 Daily Runner — {ts}")
    print(f"  Candidates limit: {args.max_candidates}")
    print(f"  Min conviction:   {args.min_conviction}")
    print(f"{'='*60}\n")

    # Step 1: Screen for candidates
    print("📡 Scanning enrichment cache...")
    candidates = get_candidates(args.max_candidates, args.min_conviction)
    if not candidates:
        print("  No candidates found. Exiting.")
        return 0

    print(f"  Found {len(candidates)} candidate(s):")
    for c in candidates:
        print(f"    {c['ticker']:6s}  {c['direction']:6s}  {c['signal']:8s}  "
              f"conviction={c['conviction']}/10")
    print()

    if args.dry_run:
        print("🏁 Dry run — pipeline skipped. Exiting.")
        return 0

    # Step 2: Run pipeline for each candidate
    results = []
    for i, c in enumerate(candidates, 1):
        ticker = c["ticker"]
        direction = c["direction"]
        pip_out = output_dir / f"{ticker}.json"

        print(f"  [{i}/{len(candidates)}] 🧪 {ticker} ({direction})...", end=" ", flush=True)
        try:
            pipeline_result = run_pipeline(ticker, direction, pip_out)
            c["pipeline_result"] = pipeline_result
            results.append(c)
            # Print inline result
            final = pipeline_result.get("final", {})
            judge = pipeline_result.get("stages", {}).get("judge", {})
            verdict = judge.get("verdict", "?")
            conviction = judge.get("conviction_score", 0)
            action = final.get("action", "?")
            print(f"verdict={verdict} conviction={conviction} action={action}")
        except Exception as e:
            c["error"] = str(e)
            c["pipeline_result"] = {"status": "FAILED", "error": str(e)}
            results.append(c)
            print(f"❌ FAILED: {e}")

    print()

    # Step 3: Generate and write digest
    digest = generate_digest(results, run_id)
    digest_path = write_digest(digest, digest_dir)
    clean_old_digests(digest_dir)

    # Step 4: Run calibration loop (post-digest verification + scoring)
    calibration_digest = digest_path
    if digest_path.exists():
        try:
            sys.path.insert(0, str(CALIBRATION_DIR))
            from calibration_runner import run_calibration  # type: ignore
            cal_result = run_calibration(digest_path=digest_path)
            if cal_result:
                print(f"  📈 Calibration: {cal_result}")
        except Exception as e:
            print(f"  ⚠️  Calibration skipped: {e}")

    notable = [e for e in digest["entries"] if e["can_execute"]]

    # Print summary
    print(f"{'='*60}")
    print(f"  📊 D-013 Daily Digest — {run_id}")
    print(f"  Candidates: {digest['total_candidates']}  |  Notable: {digest['notable_count']}  |  "
          f"Executable: {len(notable)}")
    print(f"  Digest: {digest_path}")
    print(f"  Outputs: {output_dir}")
    print()

    if notable:
        print("  ⚡ Notable verdicts (actionable):")
        for e in notable:
            print(f"    🔴 {e['ticker']:6s}  {e['direction']:6s}  "
                  f"judge={e['judge_verdict']}  conv={e['judge_conviction']}  "
                  f"veto={e['veto_power_level']}")
    else:
        print("  No executable thesis today.")

    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
