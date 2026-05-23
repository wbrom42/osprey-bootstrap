"""
D-013-002: VetoEngine — Graduated Powers Implementation

Graduated powers processing for thesis pipeline. Operates as a gate between
the JUDGE verdict and the SIZE step. Provides four power levels:

  - APPROVE — thesis passes through to SIZE without modification
  - REDUCE  — reduces position sizing (conviction-adjusted scaling)
  - DELAY   — holds the thesis for later review (cooldown period)
  - REJECT  — kills the thesis (no path to execution)

Each power level has:
  1. A clear threshold or rule trigger
  2. Structured output with rationale
  3. Event logging integration

Usage:
    python3 veto_engine.py --action action.json
    python3 veto_engine.py --thesis thesis.json --verdict debate_verdict.json
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


# ── Power Levels ─────────────────────────────────────────────────────────

class PowerLevel(str, Enum):
    APPROVE = "APPROVE"      # Full pass-through
    REDUCE = "REDUCE"        # Reduced sizing (multiplicative factor)
    DELAY = "DELAY"          # Deferred review with cooldown
    REJECT = "REJECT"        # Thesis killed

    def __str__(self) -> str:
        return self.value


# ── Veto Result Schema ───────────────────────────────────────────────────

class VetoResult:
    """Structured output of a VetoEngine evaluation."""

    def __init__(
        self,
        power_level: PowerLevel,
        reason: str,
        reduction_factor: float | None = None,
        delay_hours: int | None = None,
        override_conviction: float | None = None,
        triggered_rules: list[str] | None = None,
        veto_id: str | None = None,
    ):
        self.veto_id = veto_id or str(uuid.uuid4())
        self.power_level = power_level
        self.reason = reason
        self.reduction_factor = reduction_factor
        self.delay_hours = delay_hours
        self.override_conviction = override_conviction
        self.triggered_rules = triggered_rules or []
        self.evaluated_at = datetime.now(timezone.utc).isoformat()
        self.approved = power_level == PowerLevel.APPROVE

    def to_dict(self) -> dict:
        return {
            "veto_id": self.veto_id,
            "power_level": self.power_level.value,
            "approved": self.approved,
            "reason": self.reason,
            "reduction_factor": self.reduction_factor,
            "delay_hours": self.delay_hours,
            "override_conviction": self.override_conviction,
            "triggered_rules": self.triggered_rules,
            "evaluated_at": self.evaluated_at,
        }

    def to_action_doc(self) -> dict:
        """Convert to JUDGE-compatible action document for gate evaluation."""
        return {
            "veto_id": self.veto_id,
            "veto_verdict": self.power_level.value,
            "reason": self.reason,
            "reduction_factor": self.reduction_factor,
            "delay_hours": self.delay_hours,
            "override_conviction": self.override_conviction,
            "triggered_rules": self.triggered_rules,
            "evaluated_at": self.evaluated_at,
        }


# ── VetoEngine Core ─────────────────────────────────────────────────────

class VetoEngine:
    """Graduated powers engine for thesis pipeline.

    Evaluates a thesis + judge verdict against rule-based triggers and
    conviction/risk thresholds to produce a power level decision.
    """

    def __init__(self, rules: list[dict] | None = None):
        self.rules = rules or []
        self._history: list[VetoResult] = []

    def evaluate(
        self,
        thesis: dict,
        debate_transcript: dict | None = None,
        judge_verdict: dict | None = None,
        portfolio_context: dict | None = None,
    ) -> VetoResult:
        """Evaluate a thesis through the graduated powers engine.

        Stages:
        1. Run all registered rules → aggregate triggered rules
        2. Evaluate base approval from JUDGE verdict
        3. Apply REDUCE / DELAY / REJECT based on triggered rules and risk
        4. Fall through to APPROVE if no rules trigger a block

        Args:
            thesis: Structured thesis dict
            debate_transcript: Optional debate transcript
            judge_verdict: Optional judge verdict dict with conviction_score etc.
            portfolio_context: Optional portfolio context dict

        Returns:
            VetoResult with power level decision
        """
        triggered_rules = self._evaluate_rules(thesis, portfolio_context)

        # Default to approve
        power_level = PowerLevel.APPROVE
        reason = "Veto gate: APPROVE — no blocking rules triggered"
        reduction_factor = None
        delay_hours = None
        override_conviction = None

        # Check for hard block / reject
        reject_rules = [r for r in triggered_rules if r.get("level") == "REJECT"]
        if reject_rules:
            reasons = [r.get("reason", "Rule rejection") for r in reject_rules]
            power_level = PowerLevel.REJECT
            reason = f"Veto gate: REJECT — {'; '.join(reasons)}"
            return self._record(power_level, reason, triggered_rules=triggered_rules)

        # Check for delay
        delay_rules = [r for r in triggered_rules if r.get("level") == "DELAY"]
        if delay_rules:
            reasons = [r.get("reason", "Rule delay") for r in delay_rules]
            delay_hours = max(r.get("delay_hours", 24) for r in delay_rules)
            power_level = PowerLevel.DELAY
            reason = f"Veto gate: DELAY ({delay_hours}h) — {'; '.join(reasons)}"
            return self._record(
                power_level, reason, delay_hours=delay_hours,
                triggered_rules=triggered_rules,
            )

        # Check for reduction based on conviction or rules
        reduce_rules = [r for r in triggered_rules if r.get("level") == "REDUCE"]

        # Also check judge verdict for low conviction
        judge_conviction = None
        if judge_verdict:
            judge_conviction = judge_verdict.get("conviction_score")
        thesis_conviction = thesis.get("conviction", 5)

        # Determine if reduction is needed based on conviction level
        conviction_needs_reduce = self._evaluate_conviction_reduction(thesis_conviction, judge_conviction)

        if reduce_rules or conviction_needs_reduce:
            rules_reason = [r.get("reason", "Rule reduction") for r in reduce_rules]
            reasons_list = rules_reason
            if conviction_needs_reduce:
                reasons_list.append(f"Low conviction: {judge_conviction or thesis_conviction}/10")

            reduction_factor = self._calculate_reduction(reduce_rules,
                                                          thesis_conviction,
                                                          judge_conviction)
            power_level = PowerLevel.REDUCE
            reason = f"Veto gate: REDUCE (factor: {reduction_factor}) — {'; '.join(reasons_list)}"
            override_conviction = (judge_conviction or thesis_conviction) * reduction_factor
            return self._record(
                power_level, reason, reduction_factor=reduction_factor,
                override_conviction=override_conviction,
                triggered_rules=triggered_rules,
            )

        # APPROVE - pass through
        return self._record(
            PowerLevel.APPROVE, reason,
            triggered_rules=triggered_rules,
        )

    def _evaluate_conviction_reduction(
        self, thesis_conviction: float, judge_conviction: float | None
    ) -> bool:
        """Check if conviction level triggers a reduction.

        Rules:
        - thesis_conviction < 4 → REDUCE
        - judge_conviction < 4 → REDUCE
        - thesis or judge conviction in [4, 6) → REDUCE (moderate reduction)
        - thesis or judge conviction >= 6 → no reduction from conviction alone
        """
        primary = judge_conviction or thesis_conviction
        return primary < 6.0 if primary else True

    def _calculate_reduction(
        self,
        reduce_rules: list[dict],
        thesis_conviction: float,
        judge_conviction: float | None,
    ) -> float:
        """Calculate the reduction factor (0.0 - 1.0).

        Factors:
        - Minimum reduction from conviction level
        - Additional reduction from triggered rules
        - Floor at 0.25 (never reduce below 25% of original)
        """
        primary = judge_conviction or thesis_conviction

        # Base reduction from conviction
        if primary < 4.0:
            base = 0.4  # 60% reduction
        elif primary < 6.0:
            base = 0.7  # 30% reduction
        else:
            base = 1.0  # no reduction from conviction

        # Additional reduction from rules
        rule_reductions = [r.get("reduction_factor", 1.0) for r in reduce_rules]
        for rule_factor in rule_reductions:
            base *= rule_factor

        return max(0.25, base)

    def _evaluate_rules(
        self, thesis: dict, portfolio_context: dict | None
    ) -> list[dict]:
        """Run all registered rules against the thesis and context.

        Returns list of triggered rule results with level, reason, and params.
        """
        triggered = []
        for rule in self.rules:
            result = rule.evaluate(thesis, portfolio_context)
            if result is not None:
                triggered.append(result)
        return triggered

    def _record(
        self,
        power_level: PowerLevel,
        reason: str,
        reduction_factor: float | None = None,
        delay_hours: int | None = None,
        override_conviction: float | None = None,
        triggered_rules: list | None = None,
    ) -> VetoResult:
        result = VetoResult(
            power_level=power_level,
            reason=reason,
            reduction_factor=reduction_factor,
            delay_hours=delay_hours,
            override_conviction=override_conviction,
            triggered_rules=[r.get("rule_name", str(r)) for r in (triggered_rules or [])],
        )
        self._history.append(result)
        return result

    def get_history(self) -> list[VetoResult]:
        """Return all evaluations made by this engine instance."""
        return list(self._history)

    @property
    def approval_rate(self) -> float:
        """Calculate overall approval rate from history."""
        if not self._history:
            return 0.0
        approved = sum(1 for r in self._history if r.approved)
        return approved / len(self._history)


# ── VetoEngine Gate (JUDGE-compatible wrapper) ──────────────────────────

def veto_engine_gate(
    thesis: dict,
    debate_transcript: dict | None = None,
    judge_verdict: dict | None = None,
    portfolio_context: dict | None = None,
    rules: list | None = None,
) -> dict:
    """Wrapper that runs VetoEngine and returns a JUDGE-compatible result.

    Returns dict with:
        verdict: One of [APPROVE, REVISE, BLOCK]
        gate: "veto_engine"
        power_level: The VetoEngine power level
        reason: Full rationale
        veto_result: Complete veto result dict
    """
    engine = VetoEngine(rules=rules or [])
    result = engine.evaluate(thesis, debate_transcript, judge_verdict, portfolio_context)

    # Map to JUDGE verdict
    if result.power_level == PowerLevel.APPROVE:
        verdict = "APPROVE"
    elif result.power_level == PowerLevel.REDUCE:
        verdict = "APPROVE"  # Still approves, just with reduced sizing
    elif result.power_level == PowerLevel.DELAY:
        verdict = "REVISE"
    elif result.power_level == PowerLevel.REJECT:
        verdict = "BLOCK"
    else:
        verdict = "BLOCK"

    return {
        "verdict": verdict,
        "gate": "veto_engine",
        "power_level": result.power_level.value,
        "reason": result.reason,
        "veto_result": result.to_dict(),
    }


# ── Rule Base Class ─────────────────────────────────────────────────────

class VetoRule:
    """Base class for VetoEngine rules.

    Subclasses implement evaluate() which returns a rule trigger dict or None.
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def evaluate(self, thesis: dict, portfolio_context: dict | None = None) -> dict | None:
        """Evaluate rule against thesis and context.

        Returns dict with keys:
            level: Power level triggered (REJECT/DELAY/REDUCE)
            reason: Human-readable reason
            rule_name: Name of the triggered rule
            Plus optional params (delay_hours, reduction_factor, etc.)

        Returns None if rule does not trigger.
        """
        raise NotImplementedError


# ── CLI ─────────────────────────────────────────────────────────────────

def _load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="D-013 VetoEngine — Graduated Powers")
    parser.add_argument("--thesis", help="Thesis JSON file path")
    parser.add_argument("--verdict", help="Judge verdict JSON file path")
    parser.add_argument("--transcript", help="Debate transcript JSON file path (optional)")
    parser.add_argument("--portfolio", help="Portfolio context JSON file path (optional)")
    parser.add_argument("--action", help="Combined action JSON file path")
    parser.add_argument("--output", default="veto_result.json", help="Output path")
    args = parser.parse_args()

    rules: list[VetoRule] = []

    # Load inputs
    if args.action:
        action = _load_json(args.action)
        thesis = action.get("thesis", {})
        debate_transcript = action.get("debate_transcript")
        judge_verdict = action.get("judge_verdict")
        portfolio_context = action.get("portfolio_context")
    else:
        thesis = _load_json(args.thesis) if args.thesis else {}
        debate_transcript = _load_json(args.transcript) if args.transcript else None
        judge_verdict = _load_json(args.verdict) if args.verdict else None
        portfolio_context = _load_json(args.portfolio) if args.portfolio else None

    # Import veto rules
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from veto_rules import DEFAULT_RULES
        rules = DEFAULT_RULES
    except ImportError:
        print("⚠️  No veto_rules module found, using empty ruleset")

    # Run VetoEngine
    engine = VetoEngine(rules=rules)
    result = engine.evaluate(thesis, debate_transcript, judge_verdict, portfolio_context)

    # Gate wrapper
    gate_result = veto_engine_gate(
        thesis, debate_transcript, judge_verdict, portfolio_context, rules
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "veto_result": result.to_dict(),
        "gate_result": gate_result,
        "engine_history": [r.to_dict() for r in engine.get_history()],
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"✅ VetoEngine: {result.power_level}")
    print(f"   Reason: {result.reason}")
    if result.reduction_factor:
        print(f"   Reduction factor: {result.reduction_factor}")
    if result.delay_hours:
        print(f"   Delay: {result.delay_hours}h")
    print(f"   Gate verdict: {gate_result['verdict']}")
    print(f"   Output: {output_path}")


if __name__ == "__main__":
    main()
