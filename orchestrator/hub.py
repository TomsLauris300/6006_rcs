"""Orchestrator Hub: dispatches batched tasks to specialized agents in parallel.

Design notes
------------
The hub does not itself call out to an LLM to plan — Tom (or a separate
planner agent) submits a batch of self-contained pasteables. The hub:

1. Writes each task to the file queue (atomic rename).
2. Spawns one subprocess per task via `AgentRunner`, in parallel up to
   `max_workers`.
3. Captures stdout/stderr to `.orchestrator/logs/<task_id>.log`.
4. Writes a `Result` JSON to `.orchestrator/results/<task_id>.json`.
5. Returns a list of results once every task settles.

A `planner` agent prompt is included for the case where Tom wants the hub
to decompose a goal: submit a single planner task, parse its JSON output
(an array of pasteables), then dispatch the resulting batch.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Sequence

from .agent import AgentConfig, AgentRunner
from .queue import TaskQueue
from .schema import AgentType, Result, Task, TaskStatus
from .state import State

log = logging.getLogger(__name__)


def _default_root(vault_root: Path) -> Path:
    return vault_root / ".orchestrator"


class OrchestratorHub:
    def __init__(
        self,
        vault_root: Path | str,
        max_workers: int = 4,
        agent_config: AgentConfig | None = None,
    ):
        self.vault_root = Path(vault_root).expanduser().resolve()
        self.queue = TaskQueue(_default_root(self.vault_root))
        self.queue.ensure_dirs()
        self.runner = AgentRunner(self.vault_root, agent_config)
        self.state = State(self.queue.state_dir)
        self.max_workers = max(1, max_workers)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def dispatch_batch(
        self,
        tasks: Sequence[Task],
        goal: str = "",
        run_id: str | None = None,
        on_complete: Callable[[Result], None] | None = None,
    ) -> list[Result]:
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.state.start_run(goal or "(no goal description)", run_id)

        for t in tasks:
            self.queue.enqueue(t)
            self.state.record_task(run_id, t)

        results: list[Result] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_one, t, run_id): t for t in tasks}
            for fut in as_completed(futures):
                result = fut.result()
                results.append(result)
                if on_complete is not None:
                    try:
                        on_complete(result)
                    except Exception:
                        log.exception("on_complete callback raised")

        self.state.finish_run(run_id)
        return results

    def plan_and_dispatch(
        self,
        goal: str,
        context: dict | None = None,
        max_workers: int | None = None,
    ) -> tuple[Result, list[Result]]:
        """Submit a planner task, parse it, then dispatch the resulting batch."""
        planner_task = Task.new(
            agent_type=AgentType.PLANNER,
            instructions=goal,
            context=context or {},
            expected_output_format="json",
        )
        plan_result = self._run_one(planner_task, run_id=None)
        if plan_result.status != TaskStatus.COMPLETED:
            return plan_result, []

        sub_tasks = parse_plan(plan_result.output, parent_id=planner_task.task_id)
        if max_workers is not None:
            self.max_workers = max(1, max_workers)
        batch_results = self.dispatch_batch(sub_tasks, goal=goal)
        return plan_result, batch_results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _run_one(self, task: Task, run_id: str | None) -> Result:
        if run_id is not None:
            self.state.update_task_status(run_id, task.task_id, TaskStatus.RUNNING)
        result = self.runner.run(task, log_path=self.queue.log_path(task.task_id))
        self.queue.write_result(result)
        if run_id is not None:
            self.state.update_task_status(run_id, task.task_id, result.status)
        return result


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", re.DOTALL)


def parse_plan(planner_output: str, parent_id: str | None = None) -> list[Task]:
    """Extract a JSON array of pasteables from a planner agent's output.

    Accepts either a raw JSON array or a fenced ```json block. Each entry
    must have `agent_type` and `instructions`; `context` and
    `expected_output_format` are optional.
    """
    text = planner_output.strip()
    candidates: list[str] = []
    m = _JSON_BLOCK_RE.search(text)
    if m:
        candidates.append(m.group(1))
    candidates.append(text)

    last_err: Exception | None = None
    for raw in candidates:
        try:
            data = json.loads(raw)
            break
        except json.JSONDecodeError as e:
            last_err = e
    else:
        raise ValueError(f"Could not parse planner output as JSON: {last_err}")

    if not isinstance(data, list):
        raise ValueError("Planner output must be a JSON array of task objects")

    tasks: list[Task] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"Planner entry must be an object, got {type(entry)}")
        tasks.append(
            Task.new(
                agent_type=entry["agent_type"],
                instructions=entry["instructions"],
                context=entry.get("context", {}),
                parent_id=parent_id,
                expected_output_format=entry.get("expected_output_format", "markdown"),
            )
        )
    return tasks
