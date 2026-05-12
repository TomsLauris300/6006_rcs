"""Persistent state for the orchestrator.

The state file lives at `.orchestrator/state/state.json` inside the vault. It
records every dispatched task so an interrupted run can be resumed: tasks
whose results already exist are skipped, and tasks still listed as RUNNING
are re-dispatched.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .schema import Task, TaskStatus

STATE_FILENAME = "state.json"


class State:
    def __init__(self, state_dir: Path | str):
        self.path = Path(state_dir) / STATE_FILENAME
        self._data: dict[str, Any] = {"runs": {}, "current_run": None}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self._data = {"runs": {}, "current_run": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        os.replace(tmp, self.path)

    def start_run(self, goal: str, run_id: str) -> None:
        with self._lock:
            self._data["current_run"] = run_id
            self._data["runs"][run_id] = {
                "goal": goal,
                "started_at": time.time(),
                "finished_at": None,
                "tasks": {},
            }
            self._save()

    def record_task(self, run_id: str, task: Task) -> None:
        with self._lock:
            run = self._data["runs"].setdefault(run_id, {"tasks": {}})
            run.setdefault("tasks", {})[task.task_id] = {
                "agent_type": task.agent_type.value,
                "status": task.status.value,
                "instructions_preview": task.instructions[:200],
            }
            self._save()

    def update_task_status(self, run_id: str, task_id: str, status: TaskStatus) -> None:
        with self._lock:
            run = self._data["runs"].get(run_id)
            if not run:
                return
            entry = run.get("tasks", {}).get(task_id)
            if entry is None:
                return
            entry["status"] = status.value
            self._save()

    def finish_run(self, run_id: str) -> None:
        with self._lock:
            run = self._data["runs"].get(run_id)
            if run is not None:
                run["finished_at"] = time.time()
            if self._data.get("current_run") == run_id:
                self._data["current_run"] = None
            self._save()

    @property
    def current_run(self) -> str | None:
        return self._data.get("current_run")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._data["runs"].get(run_id)
