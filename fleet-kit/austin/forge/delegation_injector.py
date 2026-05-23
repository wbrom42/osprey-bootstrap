"""Delegation Injector — MUST be called before every delegate_task().

Generates the framework compliance context that gets injected into every
child agent's ``context`` field. This is Layer 1 enforcement — push-based,
run at the delegation boundary.

Usage (inside execute_code or as a pre-delegation step):

    from osprey.enforcement.delegation_injector import build_delegation_context

    context = build_delegation_context(
        task_goal="Implement feature X",
        scope_packet_path="handoffs/inbox/real/SCOPE-20260516-xxx.approval.json",
        task_id="T-001",
    )
    # Then call delegate_task(context=context, ...)

Frame rules injected into every child agent's system context:
  - Must load scope packet before any execution
  - Must run provenance gate before write operations
  - Must log decisions to Event Store
  - Must use orchestration engine for multi-step workflows
  - Must write fix records on errors
"""

from __future__ import annotations

import textwrap
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────

SPARK_VAULT = Path.home() / "spark-vault"


def build_delegation_context(
    task_goal: str = "",
    scope_packet_path: str = "",
    task_id: str = "",
    extra_instructions: str = "",
) -> str:
    """Build the framework compliance context for a delegate_task() call.

    Args:
        task_goal: What the task is supposed to achieve (e.g. 'Build feature X').
        scope_packet_path: Path to the approved scope packet JSON (relative to spark-vault/).
        task_id: A unique identifier for this task (e.g. 'T-001', 'H-001').
        extra_instructions: Additional task-specific instructions appended at the end.

    Returns:
        A string ready for use as delegate_task()'s ``context`` parameter.
        The string is structured as: task description → framework requirements →
        scope reference → extra instructions.
    """
    parts = [f"## Task\n{task_goal}"]

    # ── Framework compliance requirements ───────────────────────────────
    parts.append(textwrap.dedent("""
        ## Framework Compliance (MANDATORY — enforced at delegation boundary)

        You MUST comply with the Osprey framework for all work in this task.
        Bypassing or ignoring any of these requirements is a protocol violation
        that will be caught by the compliance audit cron.

        ### Scope Packet
        - Load the approved scope packet for this task BEFORE any execution.
        - Verify the scope packet's EC classification, authority tier, and risk level.
        - Do not exceed the authority granted by the scope packet.

        ### Provenance Gate
        - Run ``python3 {SPARK_VAULT}/osprey/doctrine/provenance_gate.py``
          before any write operation (file creation, terminal execution with
          side-effects, any mutation).
        - Log the gate result to the Event Store via:
          ``python3 -c "from osprey.event_store.store import EventStore; ..."``
          OR through the orchestration engine.

        ### Event Store
        - Log ALL decisions, state transitions, and outcomes to
          ``event_store_v2.db`` (osprey/event_store/).
        - Use the Event dataclass from ``osprey.event_store.schema``.

        ### Orchestration Engine
        - For multi-step workflows, use the engine at
          ``{SPARK_VAULT}/osprey/orchestration/engine.py``.
        - Do NOT chain multiple terminal() calls as a substitute for a workflow DAG.

        ### Fix Records
        - On errors, write a structured fix record to osprey/fix_records/.
        - Include causation chain referencing the Event Store event_id.

        ### Compensation
        - For reversible steps, register compensation handlers with
          osprey/compensation/controller.py.
        - On failure, trigger rollback via the RollbackController.

        Failure to comply will be detected by the daily compliance audit cron
        and flagged to The Forge for remediation.
    """))

    # ── Scope packet reference ──────────────────────────────────────────
    if scope_packet_path:
        parts.append(f"\n### Scope Packet Reference\n{scope_packet_path}")

    # ── Task identifier ─────────────────────────────────────────────────
    if task_id:
        parts.append(f"\n### Task ID\n{task_id}")

    # ── Extra instructions ──────────────────────────────────────────────
    if extra_instructions:
        parts.append(f"\n### Additional Instructions\n{extra_instructions}")

    return "\n".join(parts)


def build_scope_packet_path(name: str) -> str:
    """Build a conventional scope packet path from a short name.

    Example::
        build_scope_packet_path("ec-001-implement-feature")
        # → "handoffs/inbox/real/SCOPE-ec-001-implement-feature.approval.json"
    """
    return f"handoffs/inbox/real/SCOPE-{name}.approval.json"
