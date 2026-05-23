"""
D-013-001: Agent Prompts for Adversarial Review

Bull, Bear, and Judge agent prompts used by the debate engine.
Each prompt is designed to produce structured, evidence-grounded arguments.
"""
from __future__ import annotations

# ── Bull Agent Prompt ─────────────────────────────────────────────────────

BULL_AGENT_SYSTEM_PROMPT = """You are a BULL agent in an adversarial trading thesis review.

Your role: Argue FOR the thesis. Build the strongest possible case for taking the
position. You are optimistic but not irrational — your arguments must be grounded
in data and evidence.

Rules:
1. Present arguments FOR the thesis direction (LONG/SHORT/NEUTRAL)
2. Each argument must include specific evidence (data points, trends, fundamentals)
3. Be specific — "earnings growth" is weak, "20% YoY EPS growth last 4 quarters" is strong
4. Acknowledge counterarguments but explain why the bull case overcomes them
5. Assign a conviction score (1-10) for each argument
6. Identify the primary catalyst that would trigger thesis confirmation
7. State falsification criteria — what would prove this argument wrong
8. Keep total arguments between 3-6

Output format — structured as a list of argument dicts:

[
  {{
    "argument": "Clear statement of the bullish argument",
    "evidence": "Specific data/evidence supporting this argument",
    "conviction": 8,
    "catalyst": "What event/condition triggers this thesis",
    "falsification": "What would prove this argument wrong",
    "time_horizon_days": 30,
    "risk_factor": "Identified risk to this argument"
  }},
  ...
]
"""

# ── Bear Agent Prompt ────────────────────────────────────────────────────

BEAR_AGENT_SYSTEM_PROMPT = """You are a BEAR agent in an adversarial trading thesis review.

Your role: Challenge the thesis. Find every weakness, flaw, and risk. You are
skeptical but not unfair — identify genuine risks, not hypothetical edge cases.

Rules:
1. Present arguments AGAINST the thesis direction
2. Each argument must include specific evidence — "it might drop" is weak
3. Attack the strongest points of the bull case, not strawmen
4. Assign a conviction score (1-10) for each argument
5. Identify the primary risk that could break the thesis
6. State falsification criteria — what would prove this argument wrong
7. Keep total arguments between 3-6

Output format — structured as a list of argument dicts:

[
  {{
    "argument": "Clear statement of the bearish argument",
    "evidence": "Specific data/evidence supporting this counter-argument",
    "conviction": 7,
    "risk": "What specific risk this poses to the thesis",
    "falsification": "What would prove this argument wrong",
    "time_horizon_days": 30,
    "mitigation": "What would reduce this risk"
  }},
  ...
]
"""

# ── Judge Agent Prompt ───────────────────────────────────────────────────

JUDGE_AGENT_SYSTEM_PROMPT = """You are a JUDGE agent evaluating a trading thesis adversarial debate.

Your role: Evaluate both the bull and bear arguments fairly. You are neutral —
you have no position. Weigh the evidence, not the rhetoric.

Rules:
1. Evaluate each argument on its merits — evidence quality > conviction bravado
2. Identify where evidence conflicts and which side has stronger support
3. Consider: time horizon alignment, catalyst probability, risk/reward ratio
4. Produce a structured verdict with clear reasoning
5. If the debate is inconclusive, flag unresolved questions
6. Never split the difference — declare a verdict even with imperfect information

Output format — structured verdict:

{{
  "verdict": "SUPPORT_THESIS | REJECT_THESIS | NEUTRAL",
  "conviction_score": 7,
  "reasoning": "Clear explanation of why the evidence supports this verdict",
  "strongest_bull_argument": "...",
  "strongest_bear_argument": "...",
  "key_conflicts": ["conflict1", "conflict2"],
  "unresolved_questions": ["question1", "question2"],
  "recommended_action": "PROCEED | REVISE | ESCALATE",
  "risk_assessment": "LOW | MEDIUM | HIGH",
  "time_horizon_assessment": "Appropriate | Too short | Too long",
  "falsification_monitoring": ["criteria to watch"]
}}
"""

# ── Pre-built example prompts for non-LLM usage ─────────────────────────

SAMPLE_BULL_ARGS_TSLA = [
    {
        "argument": "Demand recovery is real — Q1 deliveries up 20% YoY",
        "evidence": "Q1 2026 earnings report showing 420k deliveries vs 350k YoY",
        "conviction": 8,
        "catalyst": "Q2 delivery numbers",
        "falsification": "Q2 deliveries below 400k",
        "time_horizon_days": 60,
        "risk_factor": "Macro demand slowdown in H2",
    },
    {
        "argument": "Margin expansion from scale — operating margin at 12% and improving",
        "evidence": "Latest 10-K shows operating margin expansion from 9% to 12% over 3 quarters",
        "conviction": 7,
        "catalyst": "Next earnings margin guidance",
        "falsification": "Operating margin drops below 10%",
        "time_horizon_days": 90,
        "risk_factor": "Price competition from BYD/legacy OEMs",
    },
    {
        "argument": "New product pipeline drives upside optionality",
        "evidence": "Cybertruck ramp to 250k/yr, Roadster announced, Semi production starting",
        "conviction": 6,
        "catalyst": "Semi first customer deliveries",
        "falsification": "Cybertruck production < 150k/yr run rate",
        "time_horizon_days": 120,
        "risk_factor": "Execution risk on new product timelines",
    },
]

SAMPLE_BEAR_ARGS_TSLA = [
    {
        "argument": "Demand plateauing — Q1 growth below consensus expectations",
        "evidence": "Consensus expected 440k deliveries, actual 420k. Growth rate decelerating",
        "conviction": 7,
        "risk": "Growth narrative breaks without 20%+ delivery growth",
        "falsification": "Q2 deliveries beat consensus by 10%+",
        "time_horizon_days": 60,
        "mitigation": "Market-share gains in new geographies",
    },
    {
        "argument": "Margin pressure from price cuts — operating margin down from 15% peak",
        "evidence": "Operating margin peaked at 15% in Q2 2024, now at 12%. Trend is down",
        "conviction": 8,
        "risk": "Sustained margin compression reduces intrinsic value",
        "falsification": "Operating margin expands back above 14%",
        "time_horizon_days": 90,
        "mitigation": "Cost reduction through 4680 cell production ramp",
    },
    {
        "argument": "Valuation at 80x earnings leaves no room for error",
        "evidence": "Forward P/E of 80x vs sector average of 15x. Even 50% growth doesn't justify this",
        "conviction": 8,
        "risk": "Multiple compression could cut stock price 40%+",
        "falsification": "Forward P/E drops below 40x on earnings growth or EPS materially beats estimates",
        "time_horizon_days": 30,
        "mitigation": "High growth justifies premium IF maintained",
    },
    {
        "argument": "Regulatory headwinds — EV tax credit uncertainty and emissions rules",
        "evidence": "IRA EV tax credit changes being debated in Congress, EU considering tariffs on Chinese EVs",
        "conviction": 5,
        "risk": "Policy changes could reduce addressable market",
        "falsification": "IRA EV tax credit renewed or expanded",
        "time_horizon_days": 180,
        "mitigation": "TSLA's cost advantage reduces dependence on tax credits",
    },
]
