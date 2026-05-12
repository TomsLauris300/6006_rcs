"""Command-line entry point for Tom.

Examples
--------
    # Initialize the .orchestrator/ scaffold inside a vault
    python -m orchestrator.cli init /path/to/vault

    # Submit a batch from a JSON file (array of pasteables)
    python -m orchestrator.cli run /path/to/vault --batch tasks.json

    # Submit a single task on the command line
    python -m orchestrator.cli run /path/to/vault \
        --agent coder --instructions "Add a foo() to bar.py"

    # Decompose a goal via the planner agent and dispatch the result
    python -m orchestrator.cli plan /path/to/vault \
        --goal "Refactor the ingestion pipeline and write a design note"

    # Inspect state / results for the most recent run
    python -m orchestrator.cli status /path/to/vault
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .hub import OrchestratorHub
from .logging_setup import configure
from .queue import TaskQueue
from .schema import AgentType, Task

log = logging.getLogger("orchestrator.cli")


def _report(results) -> int:
    failures = [r for r in results if r.status.value != "completed"]
    print()
    print(f"Dispatched {len(results)} task(s); {len(failures)} failed.")
    for r in results:
        marker = "OK " if r.status.value == "completed" else "FAIL"
        print(f"  [{marker}] {r.task_id} ({r.agent_type.value}) {r.duration_s:.1f}s")
        if r.error:
            print(f"        error: {r.error.splitlines()[0][:160]}")
    return 1 if failures else 0


def cmd_init(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser().resolve()
    q = TaskQueue(vault / ".orchestrator")
    q.ensure_dirs()
    print(f"Initialized {q.root}")
    print("  tasks/, results/, errors/, logs/, state/")

    template = Path(__file__).parent.parent / "templates" / "CLAUDE.md"
    target = vault / "CLAUDE.md"
    if template.exists() and not target.exists():
        target.write_text(template.read_text())
        print(f"Wrote {target}")
    elif target.exists():
        print(f"Skipped {target} (already exists)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser().resolve()
    configure(vault / ".orchestrator" / "logs")

    if args.batch:
        raw = json.loads(Path(args.batch).read_text())
        if not isinstance(raw, list):
            print("--batch file must contain a JSON array", file=sys.stderr)
            return 2
        tasks = [
            Task.new(
                agent_type=entry["agent_type"],
                instructions=entry["instructions"],
                context=entry.get("context", {}),
                expected_output_format=entry.get("expected_output_format", "markdown"),
            )
            for entry in raw
        ]
    elif args.instructions:
        tasks = [
            Task.new(
                agent_type=AgentType(args.agent),
                instructions=args.instructions,
            )
        ]
    else:
        print("Provide --batch FILE or --instructions TEXT", file=sys.stderr)
        return 2

    hub = OrchestratorHub(vault, max_workers=args.workers)
    results = hub.dispatch_batch(tasks, goal=args.goal or "(cli run)")
    return _report(results)


def cmd_plan(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser().resolve()
    configure(vault / ".orchestrator" / "logs")
    hub = OrchestratorHub(vault, max_workers=args.workers)
    plan_result, batch_results = hub.plan_and_dispatch(args.goal)
    if plan_result.status.value != "completed":
        print("Planner failed:", file=sys.stderr)
        print(plan_result.error or plan_result.output, file=sys.stderr)
        return 1
    if not batch_results:
        print("Planner returned no subtasks. Check planner output:")
        print(plan_result.output)
        return 1
    return _report(batch_results)


def cmd_status(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser().resolve()
    q = TaskQueue(vault / ".orchestrator")
    pending = q.pending()
    results = list(q.all_results())
    print(f"Vault: {vault}")
    print(f"Pending tasks: {len(pending)}")
    for t in pending:
        print(f"  - {t.task_id} ({t.agent_type.value})")
    print(f"Results on disk: {len(results)}")
    for r in results[-10:]:
        print(f"  - {r.task_id} ({r.agent_type.value}) {r.status.value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orchestrator", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Scaffold .orchestrator/ inside a vault")
    init.add_argument("vault")
    init.set_defaults(func=cmd_init)

    run = sub.add_parser("run", help="Dispatch a single task or a batch")
    run.add_argument("vault")
    run.add_argument("--batch", help="Path to a JSON array of task objects")
    run.add_argument("--agent", choices=[a.value for a in AgentType], default="coder")
    run.add_argument("--instructions", help="Single-task instructions")
    run.add_argument("--goal", help="Optional description of the overall goal")
    run.add_argument("--workers", type=int, default=4)
    run.set_defaults(func=cmd_run)

    plan = sub.add_parser("plan", help="Decompose a goal with the planner, then dispatch")
    plan.add_argument("vault")
    plan.add_argument("--goal", required=True)
    plan.add_argument("--workers", type=int, default=4)
    plan.set_defaults(func=cmd_plan)

    status = sub.add_parser("status", help="Show pending tasks and recent results")
    status.add_argument("vault")
    status.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
