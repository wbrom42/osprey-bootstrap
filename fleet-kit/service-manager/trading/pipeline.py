"""
D-013-005: Thesis Pipeline — Main Orchestration Flow

Wires the full EC chain: CLASSIFY → THESIS → ADVERSARIAL_REVIEW → JUDGE → VETO → SIZE → PAPER → ACT

Each step is a function that produces a structured output dict. The pipeline
orchestrator runs the full chain and produces a complete thesis lifecycle record.

Usage:
    python3 pipeline.py --ticker AAPL --direction LONG
    python3 pipeline.py --thesis thesis.json
    python3 pipeline.py --action action.json --output pipeline_result.json

CLI:
    --ticker TICKER  Run full pipeline for a ticker (auto-classify + thesis)
    --direction DIR  Thesis direction (LONG/SHORT/NEUTRAL, default LONG)
    --thesis PATH    Use existing thesis file instead of generating one
    --portfolio PATH Portfolio context file (optional, uses default if absent)
    --output PATH    Output path (default: pipeline_result.json)
    --dry-run        Print pipeline steps without executing full chain
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path
_PROJECT_ROOT = Path.home() / "spark-vault"
sys.path.insert(0, str(_PROJECT_ROOT))

# ── Thesis Pipeline modules (same dir) ──────────────────────────────────
_PIPELINE_DIR = _PROJECT_ROOT / "projects" / "D-013" / "build" / "thesis-pipeline"

def _load_py(name, path):
    spec = _ilu.spec_from_file_location(name, str(path))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_ths = _load_py("thesis_schema", _PIPELINE_DIR / "thesis_schema.py")
create_classification = _ths.create_classification
create_thesis = _ths.create_thesis
validate_thesis = _ths.validate_thesis
mark_debated = _ths.mark_debated
mark_judged = _ths.mark_judged
mark_sized = _ths.mark_sized
mark_paper = _ths.mark_paper
mark_pending_act = _ths.mark_pending_act
VALID_DIRECTIONS = _ths.VALID_DIRECTIONS
VALID_HORIZONS = _ths.VALID_HORIZONS

_se = _load_py("size_engine", _PIPELINE_DIR / "size_engine.py")
SizeEngine = _se.SizeEngine

_pc = _load_py("portfolio_context", _PIPELINE_DIR / "portfolio_context.py")
PortfolioContext = _pc.PortfolioContext
load_enrichment = _pc.load_enrichment

# ── Adversarial Review (sibling dir) ────────────────────────────────────
_ADV_DIR = _PROJECT_ROOT / "projects" / "D-013" / "build" / "adversarial-review"
try:
    _adv_mod = _load_py("adversarial_review_sibling", _ADV_DIR.parent / "adversarial_review.py")
    ADV_REVIEW_AVAILABLE = True
except Exception:
    ADV_REVIEW_AVAILABLE = False
    _adv_mod = None
adv_validate = getattr(_adv_mod, "validate_thesis", None) if _adv_mod else None
assemble_debate = getattr(_adv_mod, "assemble_debate", None) if _adv_mod else None

# ── VetoEngine (sibling dir) ────────────────────────────────────────────
_VETO_DIR = _PROJECT_ROOT / "projects" / "D-013" / "build" / "veto-engine"
VETO_AVAILABLE = False
VetoEngine = None
veto_engine_gate = None
PowerLevel = None
DEFAULT_RULES = []
try:
    _ve = _load_py("veto_engine", _VETO_DIR / "veto_engine.py")
    _vr = _load_py("veto_rules", _VETO_DIR / "veto_rules.py")
    VetoEngine = _ve.VetoEngine
    veto_engine_gate = _ve.veto_engine_gate
    PowerLevel = _ve.PowerLevel
    DEFAULT_RULES = _vr.DEFAULT_RULES
    VETO_AVAILABLE = True
except Exception:
    pass

# ── JUDGE module (osprey) ───────────────────────────────────────────────
try:
    _judge = _load_py("judge", _PROJECT_ROOT / "osprey" / "judge" / "judge.py")
    evaluate_action = _judge.evaluate_action
    JUDGE_AVAILABLE = True
except Exception:
    JUDGE_AVAILABLE = False
    evaluate_action = None


# ── Pipeline Step Functions ─────────────────────────────────────────────

def step_classify(ticker: str, source: str = "cli", enrich_data: dict | None = None) -> dict:
    """CLASSIFY step: Generate classification from ticker + source."""
    return create_classification(
        ticker=ticker,
        source_type=source,
        signal_category="manual",
        confidence=6.0,
        enrich_data=enrich_data or {},
        notes=f"CLI-triggered classification for {ticker}",
    )


def step_thesis(
    ticker: str,
    direction: str = "LONG",
    enrich_data: dict | None = None,
    classification: dict | None = None,
) -> dict:
    """THESIS step: Generate structured thesis document."""
    reasons = []
    catalysts = []
    falsification = []

    if enrich_data:
        if enrich_data.get("analyst_actions_30d", 0) > 5:
            reasons.append(f"Strong analyst activity ({enrich_data['analyst_actions_30d']} actions in 30d)")
        if enrich_data.get("insider_buys_30d", 0) > enrich_data.get("insider_sells_30d", 0):
            reasons.append("Positive insider buying signal")
        if enrich_data.get("seasonality_positive_pct", 50) > 55:
            reasons.append(f"Favorable seasonality ({enrich_data['seasonality_positive_pct']}% positive)")

    if not reasons:
        reasons.append(f"{direction} thesis based on initial classification")

    thesis = create_thesis(
        ticker=ticker,
        direction=direction,
        conviction=6.0 if enrich_data else 5.0,
        time_horizon="MEDIUM_TERM",
        reasoning=" | ".join(reasons),
        catalysts=catalysts or ["Earnings report", "Sector catalyst"],
        falsification_criteria=falsification or ["Fundamental deterioration"],
        entry_price=enrich_data.get("entry_price") if enrich_data else None,
        source="pipeline_cli",
        enrich_data=enrich_data,
    )
    return thesis


def step_adversarial_review(thesis: dict) -> dict:
    """ADVERSARIAL REVIEW step: Run bull/bear debate."""
    if ADV_REVIEW_AVAILABLE:
        try:
            _de = _load_py("debate_engine", _ADV_DIR / "debate_engine.py")
            return _de.run_debate(thesis)
        except Exception as e:
            print(f"\u26a0\ufe0f  Debate engine failed ({e}), using fallback")
    return _fallback_debate(thesis)


def _fallback_debate(thesis: dict) -> dict:
    """Simple fallback debate when full engine is unavailable."""
    conviction = thesis.get("conviction", 5)
    # Scale bull conviction based on thesis conviction
    bull_base = max(5, min(10, conviction))
    bear_base = max(3, min(8, 11 - conviction))

    bull_args = [
        {
            "argument": f"Direction {thesis.get('direction')} thesis is supported by current setup",
            "evidence": "Market conditions support this position",
            "conviction": bull_base,
            "catalyst": thesis.get("catalysts", ["Catalyst pending"])[0],
            "falsification": "Market reverses direction",
            "time_horizon_days": 30,
            "risk_factor": "Macro uncertainty",
        },
        {
            "argument": f"Thesis reasoning is sound: {thesis.get('reasoning', 'Fundamental strength')[:60]}",
            "evidence": "Fundamental analysis supports this thesis direction",
            "conviction": max(5, bull_base - 1),
            "catalyst": thesis.get("catalysts", ["Catalyst pending"])[1] if len(thesis.get("catalysts", [])) > 1 else "Earnings",
            "falsification": thesis.get("falsification_criteria", ["Fundamental deterioration"])[0],
            "time_horizon_days": 60,
            "risk_factor": "Execution risk",
        },
    ]
    bear_args = [
        {
            "argument": f"The {thesis.get('direction')} thesis faces significant headwinds",
            "evidence": "Valuation and risk factors suggest caution",
            "conviction": bear_base,
            "risk": "Thesis could fail if catalysts don't materialize",
            "falsification": "Catalysts confirm thesis direction",
            "time_horizon_days": 30,
            "mitigation": "Reduce position sizing",
        },
        {
            "argument": "Broader market conditions add uncertainty",
            "evidence": "Macroeconomic indicators show mixed signals",
            "conviction": max(3, bear_base - 1),
            "risk": "Systematic risk could override thesis-specific factors",
            "falsification": "Market conditions clearly improve",
            "time_horizon_days": 60,
            "mitigation": "Hedge with broader market position",
        },
    ]

    return assemble_debate(
        thesis=thesis,
        bull_args=bull_args,
        bear_args=bear_args,
        bull_strength="MODERATE",
        bear_strength="MODERATE",
    )


def step_judge(thesis: dict, debate_transcript: dict) -> dict:
    """JUDGE step: Evaluate debate and produce verdict."""
    if not JUDGE_AVAILABLE or evaluate_action is None:
        return _fallback_judge(debate_transcript)

    action_doc = {
        "action_type": "trading_thesis",
        "judge_verdict": "APPROVE",
        "debate_transcript": debate_transcript,
    }

    gate_result = evaluate_action(action_doc)
    if gate_result.get("verdict") != "APPROVE":
        return {
            "verdict": "REJECT_THESIS",
            "judge_status": "GATE_FAILED",
            "conviction_score": 0,
            "reasoning": f"JUDGE gate blocked: {gate_result.get('reason', 'Debate failed gate check')}",
            "gate_result": gate_result,
        }

    return _evaluate_debate(thesis, debate_transcript)


def _fallback_judge(debate_transcript: dict) -> dict:
    """Simple fallback judge when JUDGE module unavailable."""
    bull_args = debate_transcript.get("bull_arguments", [])
    bear_args = debate_transcript.get("bear_arguments", [])

    bull_conv = sum(a.get("conviction", 5) for a in bull_args) / max(len(bull_args), 1)
    bear_conv = sum(a.get("conviction", 5) for a in bear_args) / max(len(bear_args), 1)

    if bull_conv > bear_conv + 1:
        verdict = "SUPPORT_THESIS"
        score = min(10, bull_conv)
        action = "PROCEED"
    elif bear_conv > bull_conv + 1:
        verdict = "REJECT_THESIS"
        score = min(10, bear_conv)
        action = "REVISE"
    else:
        verdict = "NEUTRAL"
        score = (bull_conv + bear_conv) / 2
        action = "ESCALATE"

    return {
        "verdict": verdict,
        "judge_status": "FALLBACK",
        "conviction_score": score,
        "reasoning": f"Bull avg: {bull_conv:.1f}, Bear avg: {bear_conv:.1f}. Verdict: {verdict}.",
        "strongest_bull_argument": bull_args[0].get("argument", "") if bull_args else "",
        "strongest_bear_argument": bear_args[0].get("argument", "") if bear_args else "",
        "key_conflicts": debate_transcript.get("key_disagreements", []),
        "unresolved_questions": debate_transcript.get("unresolved_questions", []),
        "recommended_action": action,
        "risk_assessment": "MEDIUM",
        "time_horizon_assessment": "Appropriate",
        "falsification_monitoring": debate_transcript.get("thesis", {}).get("falsification_criteria", []),
    }


def _evaluate_debate(thesis: dict, debate_transcript: dict) -> dict:
    """Full judge evaluation using debate evidence."""
    bull_args = debate_transcript.get("bull_arguments", [])
    bear_args = debate_transcript.get("bear_arguments", [])
    thesis_conviction = thesis.get("conviction", 5)

    bull_avg_conv = sum(a.get("conviction", 5) for a in bull_args) / max(len(bull_args), 1)
    bear_avg_conv = sum(a.get("conviction", 5) for a in bear_args) / max(len(bear_args), 1)

    net = bull_avg_conv - bear_avg_conv
    if net >= 1.5:
        verdict = "SUPPORT_THESIS"
        score = min(10, thesis_conviction + net * 0.5)
        action = "PROCEED"
    elif net <= -1.5:
        verdict = "REJECT_THESIS"
        score = max(1, thesis_conviction + net * 0.5)
        action = "REVISE"
    else:
        verdict = "NEUTRAL"
        score = (thesis_conviction + (bull_avg_conv + bear_avg_conv) / 2) / 2
        action = "ESCALATE"

    return {
        "verdict": verdict,
        "judge_status": "FULL",
        "conviction_score": round(score, 1),
        "reasoning": (
            f"Bull case avg conviction: {bull_avg_conv:.1f}/10. "
            f"Bear case avg conviction: {bear_avg_conv:.1f}/10. "
            f"Net: {net:+.1f}. Verdict: {verdict}."
        ),
        "strongest_bull_argument": max(bull_args, key=lambda a: a.get("conviction", 0)).get("argument", ""),
        "strongest_bear_argument": max(bear_args, key=lambda a: a.get("conviction", 0)).get("argument", ""),
        "key_conflicts": debate_transcript.get("key_disagreements", []),
        "unresolved_questions": debate_transcript.get("unresolved_questions", []),
        "recommended_action": action,
        "risk_assessment": "HIGH" if bear_avg_conv > 7 else "MEDIUM" if bear_avg_conv > 5 else "LOW",
        "time_horizon_assessment": "Appropriate",
        "falsification_monitoring": thesis.get("falsification_criteria", []),
    }


def step_veto(
    thesis: dict,
    debate_transcript: dict | None = None,
    judge_verdict: dict | None = None,
    portfolio_context: dict | None = None,
) -> dict:
    """VETO step: Run VetoEngine graduated powers."""
    if not VETO_AVAILABLE:
        return {
            "power_level": "APPROVE",
            "reason": "VetoEngine not available — defaulting to APPROVE",
            "triggered_rules": [],
            "reduction_factor": 1.0,
        }

    veto_result = veto_engine_gate(
        thesis=thesis,
        debate_transcript=debate_transcript,
        judge_verdict=judge_verdict,
        portfolio_context=portfolio_context,
        rules=DEFAULT_RULES,
    )
    return veto_result.get("veto_result", veto_result)


def step_size(
    thesis: dict,
    portfolio: dict | None = None,
    veto_result: dict | None = None,
) -> dict:
    """SIZE step: Determine position size from conviction + portfolio."""
    engine = SizeEngine()
    return engine.size_position(thesis, portfolio, veto_result)


def step_paper(thesis: dict, size_decision: dict, current_price: float | None = None) -> dict | None:
    """PAPER step: Open virtual position for HOT signal sources only."""
    try:
        from paper_book_paper_book import open_paper_position
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "paper-book"))
        from paper_book import open_paper_position

    price = current_price or size_decision.get("entry_price", 0)
    if price <= 0:
        return None

    result = open_paper_position(thesis, price)
    if result:
        return {
            "position_id": result["position_id"],
            "ticker": result["ticker"],
            "entry_price": result["entry_price"],
            "size_shares": result.get("size_shares", 0),
            "notional": result.get("notional", 0),
            "source": result.get("signal_source", result.get("source", "unknown")),
            "horizon_date": result.get("horizon_date", ""),
            "verdict": result.get("verdict", "PAPER_TRACKED"),
            "alpaca_order_id": result.get("alpaca_order_id", "")
        }
    return {"verdict": "NOT_PROMOTED"}


def step_act(thesis: dict, size_decision: dict, judge_verdict: dict, veto_result: dict) -> dict:
    """ACT step: Produce execution recommendation."""
    can_execute = (
        judge_verdict.get("verdict") == "SUPPORT_THESIS"
        and judge_verdict.get("recommended_action") in ("PROCEED",)
        and veto_result.get("power_level", "APPROVE") in ("APPROVE", "REDUCE")
        and size_decision.get("risk_budget_ok", True)
        and size_decision.get("recommended_value", 0) > 0
    )

    return {
        "action": "EXECUTE" if can_execute else "HOLD",
        "reason": (
            f"Recommendation: {'EXECUTE' if can_execute else 'HOLD'}. "
            f"Judge: {judge_verdict.get('verdict')}, "
            f"Veto: {veto_result.get('power_level', 'N/A')}, "
            f"Sizing: ${size_decision.get('recommended_value', 0):,.0f}, "
            f"Risk budget: {'OK' if size_decision.get('risk_budget_ok', False) else 'OVER'}"
        ),
        "can_execute": can_execute,
        "blockers": _get_blockers(judge_verdict, veto_result, size_decision),
        "execution_instructions": _build_instructions(thesis, size_decision) if can_execute else None,
    }


def _get_blockers(judge_verdict: dict, veto_result: dict, size_decision: dict) -> list[str]:
    """Identify what's blocking execution."""
    blockers = []
    if judge_verdict.get("verdict") != "SUPPORT_THESIS":
        blockers.append(f"Judge verdict: {judge_verdict.get('verdict')}")
    if judge_verdict.get("recommended_action") == "REVISE":
        blockers.append("Judge recommends revision")
    if veto_result.get("power_level") == "REJECT":
        blockers.append("VetoEngine: REJECT")
    if veto_result.get("power_level") == "DELAY":
        blockers.append(f"VetoEngine: DELAY ({veto_result.get('delay_hours', '?')}h)")
    if not size_decision.get("risk_budget_ok", True):
        blockers.append("Risk budget exceeded")
    if size_decision.get("recommended_value", 0) <= 0:
        blockers.append("No available cash for position")
    return blockers


def _build_instructions(thesis: dict, size_decision: dict) -> dict:
    """Build execution instructions from thesis and sizing."""
    return {
        "ticker": thesis.get("ticker"),
        "direction": thesis.get("direction"),
        "units": size_decision.get("unit_count", 0),
        "value": size_decision.get("recommended_value", 0),
        "order_type": "LIMIT",
        "limit_price": size_decision.get("entry_price", 0),
        "time_in_force": "DAY",
        "notes": thesis.get("reasoning", ""),
    }


# ── Full Pipeline ───────────────────────────────────────────────────────

def run_pipeline(
    ticker: str | None = None,
    direction: str = "LONG",
    thesis: dict | None = None,
    portfolio_context: dict | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the full thesis pipeline."""
    stages: dict[str, dict] = {}
    timeline: list[dict] = []

    if dry_run:
        print("Pipeline steps (dry-run):")
        for step in ["CLASSIFY", "THESIS", "ADVERSARIAL_REVIEW", "JUDGE", "VETO", "SIZE", "PAPER", "ACT"]:
            print(f"  \u2192 {step}")
        return {"status": "DRY_RUN", "stages": {}, "final": {}, "timeline": []}

    ticker_key = (ticker or (thesis.get("ticker") if thesis else "UNKNOWN")).upper()
    enrich_data = load_enrichment(ticker_key)

    # 1. CLASSIFY
    print(f"\U0001f7e2 CLASSIFY: {ticker_key}")
    classification = step_classify(ticker_key, enrich_data=enrich_data)
    stages["classify"] = classification
    timeline.append({"step": "CLASSIFY", "ticker": ticker_key, "status": "complete"})

    # 2. THESIS
    if thesis is None:
        print(f"\U0001f7e2   THESIS: {ticker_key} {direction}")
        thesis = step_thesis(ticker_key, direction, enrich_data, classification)
    else:
        print(f"\U0001f7e2   THESIS: loaded from input")

    thesis_errors = validate_thesis(thesis)
    if thesis_errors:
        print(f"\u274c Thesis validation failed: {thesis_errors}")
        return {"status": "FAILED", "error": f"Thesis validation: {'; '.join(thesis_errors)}", "stages": stages, "final": {}, "timeline": timeline}

    stages["thesis"] = thesis
    timeline.append({"step": "THESIS", "id": thesis.get("thesis_id"), "status": "complete"})

    # 3. ADVERSARIAL REVIEW
    print(f"\U0001f7e2   ADVERSARIAL_REVIEW: debating {thesis.get('ticker')}")
    debate = step_adversarial_review(thesis)
    thesis = mark_debated(thesis, debate)
    stages["adversarial_review"] = debate
    timeline.append({"step": "ADVERSARIAL_REVIEW", "debate_id": debate.get("debate_id"), "bull_args": len(debate.get("bull_arguments", [])), "bear_args": len(debate.get("bear_arguments", [])), "status": "complete"})

    # 4. JUDGE
    print(f"\U0001f7e2   JUDGE: evaluating debate")
    judge_verdict = step_judge(thesis, debate)
    thesis = mark_judged(thesis, judge_verdict)
    stages["judge"] = judge_verdict
    timeline.append({"step": "JUDGE", "verdict": judge_verdict.get("verdict"), "conviction": judge_verdict.get("conviction_score"), "status": "complete"})

    # 5. VETO
    print(f"\U0001f7e2   VETO: graduated powers check")
    veto_result = step_veto(thesis, debate, judge_verdict, portfolio_context)
    stages["veto"] = veto_result
    timeline.append({"step": "VETO", "power_level": veto_result.get("power_level"), "status": "complete"})

    # 6. SIZE
    print(f"\U0001f7e2   SIZE: position sizing")
    size_decision = step_size(thesis, portfolio_context, veto_result)
    thesis = mark_sized(thesis, size_decision)
    stages["size"] = size_decision
    timeline.append({"step": "SIZE", "allocation_pct": size_decision.get("recommended_pct", 0) * 100, "value": size_decision.get("recommended_value", 0), "status": "complete"})

    # 6.5. PAPER — virtual position for HOT sources only
    print(f"\U0001f7e2   PAPER: checking signal source quality")
    paper_result = step_paper(thesis, size_decision)
    stages["paper"] = paper_result or {"verdict": "NOT_PROMOTED"}
    thesis = mark_paper(thesis, paper_result)
    paper_summary = paper_result.get("position_id", "none") if paper_result else "none"
    timeline.append({"step": "PAPER", "verdict": paper_result.get("verdict", "NOT_PROMOTED") if paper_result else "NOT_PROMOTED", "position_id": paper_summary, "status": "complete"})

    # 7. ACT
    print(f"\U0001f7e2   ACT: execution recommendation")
    act_recommendation = step_act(thesis, size_decision, judge_verdict, veto_result)
    thesis = mark_pending_act(thesis, act_recommendation)
    stages["act"] = act_recommendation
    timeline.append({"step": "ACT", "action": act_recommendation.get("action"), "can_execute": act_recommendation.get("can_execute"), "status": "complete"})

    can_execute = act_recommendation.get("can_execute", False)
    status = "EXECUTION_READY" if can_execute else "BLOCKED"

    result = {
        "status": status,
        "pipeline_id": f"pip-{thesis.get('thesis_id', 'unknown')}",
        "thesis": thesis,
        "stages": stages,
        "final": {
            "action": act_recommendation.get("action"),
            "can_execute": can_execute,
            "recommendation": act_recommendation.get("reason"),
            "instructions": act_recommendation.get("execution_instructions"),
        },
        "timeline": timeline,
    }

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n\U0001f4c4 Output: {p}")

    print(f"\nPipeline: {status}")
    return result


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="D-013 Thesis Pipeline Orchestrator")
    parser.add_argument("--ticker", help="Stock ticker symbol")
    parser.add_argument("--direction", choices=VALID_DIRECTIONS, default="LONG",
                        help="Thesis direction")
    parser.add_argument("--thesis", help="Thesis JSON file path (overrides --ticker)")
    parser.add_argument("--portfolio", help="Portfolio context JSON file path")
    parser.add_argument("--output", default="pipeline_result.json", help="Output path")
    parser.add_argument("--dry-run", action="store_true", help="Print pipeline steps without execution")
    args = parser.parse_args()

    if args.dry_run:
        ticker = args.ticker or (json.load(open(args.thesis)).get("ticker") if args.thesis else "AAPL")
        run_pipeline(ticker=ticker, dry_run=True)
        sys.exit(0)

    if not args.ticker and not args.thesis:
        print("\u274c Either --ticker or --thesis is required")
        sys.exit(1)

    thesis = None
    if args.thesis:
        with open(args.thesis) as f:
            thesis = json.load(f)

    portfolio = None
    if args.portfolio:
        with open(args.portfolio) as f:
            portfolio = json.load(f)
    else:
        portfolio = PortfolioContext.from_default().to_dict()

    result = run_pipeline(
        ticker=args.ticker,
        direction=args.direction,
        thesis=thesis,
        portfolio_context=portfolio,
        output_path=args.output,
    )

    if result.get("status") == "FAILED":
        print(f"\u274c Pipeline failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    status = result.get("status", "UNKNOWN")
    if status == "EXECUTION_READY":
        print(f"\u2705 Pipeline: {status} — ready for action")
        sys.exit(0)
    else:
        print(f"\u26a0\ufe0f  Pipeline: {status} — blocked by gate checks")
        sys.exit(0)


if __name__ == "__main__":
    main()
