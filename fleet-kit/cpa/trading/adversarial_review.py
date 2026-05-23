#!/usr/bin/env python3
"""
D-013-001: Adversarial Review Module

Mandatory bull/bear debate step in the EC thesis chain, before JUDGE.

Takes a structured thesis → produces a debate transcript with both sides.
The JUDGE gate checks for `debate_transcript` presence before evaluating.

Usage:
    python3 adversarial_review.py --thesis thesis.json --output debate.json

The calling agent uses delegate_task for the actual LLM debate.
This module validates structure and assembles the transcript.
"""
import json, sys, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Schema ──────────────────────────────────────────────────────────────
REQUIRED_THESIS_FIELDS = ['ticker', 'direction', 'conviction', 'time_horizon']
OPTIONAL_THESIS_FIELDS = ['catalysts', 'falsification_criteria', 'entry_price', 'target_price', 'reasoning']

VALID_DIRECTIONS = ['LONG', 'SHORT', 'NEUTRAL']
VALID_HORIZONS = ['INTRADAY', 'SHORT_TERM', 'MEDIUM_TERM', 'LONG_TERM']

DEBATE_TRANSCRIPT_SCHEMA = {
    'thesis': {'type': 'dict', 'required': True},
    'bull_arguments': {'type': 'list', 'required': True},
    'bear_arguments': {'type': 'list', 'required': True},
    'bull_strength': {'type': 'str', 'required': True},
    'bear_strength': {'type': 'str', 'required': True},
    'key_disagreements': {'type': 'list', 'required': False},
    'unresolved_questions': {'type': 'list', 'required': False},
    'debate_id': {'type': 'str', 'required': True},
    'debated_at': {'type': 'str', 'required': True},
}

# ── Validation ──────────────────────────────────────────────────────────
def validate_thesis(thesis: dict) -> list:
    """Validate thesis structure. Returns list of errors (empty = valid)."""
    errors = []
    for field in REQUIRED_THESIS_FIELDS:
        if field not in thesis:
            errors.append(f'Missing required thesis field: {field}')
    direction = thesis.get('direction', '').upper()
    if direction and direction not in VALID_DIRECTIONS:
        errors.append(f'Invalid direction: {direction}. Valid: {VALID_DIRECTIONS}')
    horizon = thesis.get('time_horizon', '').upper()
    if horizon and horizon not in VALID_HORIZONS:
        errors.append(f'Invalid time_horizon: {horizon}. Valid: {VALID_HORIZONS}')
    return errors

def validate_debate(transcript: dict) -> list:
    """Validate debate transcript structure."""
    errors = []
    for field, spec in DEBATE_TRANSCRIPT_SCHEMA.items():
        if spec['required'] and field not in transcript:
            errors.append(f'Missing required debate field: {field}')
            continue
        val = transcript.get(field)
        if val is not None and spec['type'] == 'list' and not isinstance(val, list):
            errors.append(f'Field {field} should be a list, got {type(val).__name__}')
    return errors

# ── Debate Assembly ─────────────────────────────────────────────────────
def assemble_debate(thesis: dict, bull_args: list, bear_args: list,
                    bull_strength: str = 'MODERATE',
                    bear_strength: str = 'MODERATE') -> dict:
    """Assemble a structured debate transcript from bull/bear arguments.

    The calling agent generates bull_args and bear_args via delegate_task.
    This module validates and assembles the final transcript.

    Args:
        thesis: Structured thesis dict
        bull_args: List of dicts with 'argument' and 'evidence' keys
        bear_args: List of dicts with 'argument' and 'evidence' keys
        bull_strength: Overall bull case strength (WEAK/MODERATE/STRONG)
        bear_strength: Overall bear case strength (WEAK/MODERATE/STRONG)
    Returns:
        Structured debate transcript dict
    """
    # Find key disagreements — points where bull and bear directly conflict
    disagreements = []
    bull_keys = {a.get('argument', '')[:50] for a in (bull_args or []) if isinstance(a, dict)}
    bear_keys = {a.get('argument', '')[:50] for a in (bear_args or []) if isinstance(a, dict)}
    for a in (bull_args or []):
        if not isinstance(a, dict):
            continue
        for b in (bear_args or []):
            if not isinstance(b, dict):
                continue
            if _are_opposing(a, b):
                disagreements.append({
                    'bull': a.get('argument', ''),
                    'bear': b.get('argument', ''),
                    'evidence_conflict': a.get('evidence') != b.get('evidence'),
                })

    transcript = {
        'debate_id': str(uuid.uuid4()),
        'debated_at': datetime.now(timezone.utc).isoformat(),
        'thesis': thesis,
        'bull_arguments': bull_args or [],
        'bear_arguments': bear_args or [],
        'bull_strength': bull_strength,
        'bear_strength': bear_strength,
        'key_disagreements': disagreements,
        'unresolved_questions': [],
    }

    return transcript

def _are_opposing(a: dict, b: dict) -> bool:
    """Check if two arguments oppose each other on the same topic."""
    a_topic = a.get('argument', '').lower()[:30]
    b_topic = b.get('argument', '').lower()[:30]
    # Simple check — same topic mentioned
    return len(set(a_topic.split()) & set(b_topic.split())) >= 2

# ── CLI ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Adversarial Review — EC chain debate step')
    parser.add_argument('--thesis', required=True, help='Thesis JSON file path')
    parser.add_argument('--bull', required=True, help='Bull arguments JSON file path')
    parser.add_argument('--bear', required=True, help='Bear arguments JSON file path')
    parser.add_argument('--output', default='debate_transcript.json', help='Output path')
    parser.add_argument('--validate-only', action='store_true', help='Only validate, don\'t assemble')
    args = parser.parse_args()

    # Load thesis
    with open(args.thesis) as f:
        thesis = json.load(f)

    thesis_errs = validate_thesis(thesis)
    if thesis_errs:
        print(f'❌ Thesis validation failed:')
        for e in thesis_errs:
            print(f'  - {e}')
        sys.exit(1)
    print(f'✅ Thesis valid: {thesis.get("ticker")} {thesis.get("direction")}')

    if args.validate_only:
        sys.exit(0)

    # Load arguments
    with open(args.bull) as f:
        bull_args = json.load(f)
    with open(args.bear) as f:
        bear_args = json.load(f)

    if not isinstance(bull_args, list):
        bull_args = [bull_args]
    if not isinstance(bear_args, list):
        bear_args = [bear_args]

    # Assemble debate
    transcript = assemble_debate(thesis, bull_args, bear_args)

    # Validate assembled transcript
    errs = validate_debate(transcript)
    if errs:
        print(f'❌ Debate assembly errors:')
        for e in errs:
            print(f'  - {e}')
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(transcript, f, indent=2, default=str)

    print(f'✅ Debate transcript written: {output_path}')
    print(f'   Bull: {len(transcript["bull_arguments"])} arguments ({transcript["bull_strength"]})')
    print(f'   Bear: {len(transcript["bear_arguments"])} arguments ({transcript["bear_strength"]})')
    print(f'   Disagreements: {len(transcript["key_disagreements"])}')

if __name__ == '__main__':
    import argparse
    main()
