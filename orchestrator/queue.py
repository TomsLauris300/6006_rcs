"""File-based task queue.

Layout under the vault's `.orchestrator/` directory:

    tasks/      pending and in-flight task JSON files
    results/    completed result JSON files (keyed by task_id)
    errors/     failed task error reports
    logs/       per-task stdout/stderr captures
    state/      orchestrator state, including state.json

A task is enqueued by atomically writing `tasks/<task_id>.json`. Atomicity is
achieved by writing to a temp file and renaming, which is POSIX-atomic on the
same filesystem. Workers claim a task by renaming it to `.running` and finish
by writing a result file and unlinking the task file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .schema import Result, Task, TaskStatus


class TaskQueue:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.tasks_dir = self.root / "tasks"
        self.results_dir = self.root / "results"
        self.errors_dir = self.root / "errors"
        self.logs_dir = self.root / "logs"
        self.state_dir = self.root / "state"

    def ensure_dirs(self) -> None:
        for d in (
            self.root,
            self.tasks_dir,
            self.results_dir,
            self.errors_dir,
            self.logs_dir,
            self.state_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def result_path(self, task_id: str) -> Path:
        return self.results_dir / f"{task_id}.json"

    def error_path(self, task_id: str) -> Path:
        return self.errors_dir / f"{task_id}.json"

    def log_path(self, task_id: str) -> Path:
        return self.logs_dir / f"{task_id}.log"

    def enqueue(self, task: Task) -> Path:
        self.ensure_dirs()
        path = self.task_path(task.task_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(task.to_json())
        os.replace(tmp, path)
        return path

    def pending(self) -> list[Task]:
        self.ensure_dirs()
        out: list[Task] = []
        for p in sorted(self.tasks_dir.glob("*.json")):
            try:
                t = Task.from_file(p)
            except Exception:
                continue
            if t.status == TaskStatus.PENDING:
                out.append(t)
        return out

    def write_result(self, result: Result) -> Path:
        self.ensure_dirs()
        path = self.result_path(result.task_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(result.to_json())
        os.replace(tmp, path)
        # Remove the task file once a result exists — idempotent.
        try:
            self.task_path(result.task_id).unlink()
        except FileNotFoundError:
            pass
        if result.status == TaskStatus.FAILED:
            self.error_path(result.task_id).write_text(result.to_json())
        return path

    def get_result(self, task_id: str) -> Result | None:
        p = self.result_path(task_id)
        if not p.exists():
            return None
        return Result.from_file(p)

    def all_results(self) -> Iterable[Result]:
        self.ensure_dirs()
        for p in sorted(self.results_dir.glob("*.json")):
            try:
                yield Result.from_file(p)
            except Exception:
                continue
