"""Tests for state persistence."""

from __future__ import annotations

from pathlib import Path

from orchestrator.schema import AgentType, Task, TaskStatus
from orchestrator.state import State


def test_state_records_and_resumes(tmp_path: Path):
    s = State(tmp_path)
    t = Task.new(AgentType.CODER, "do X")
    s.start_run("goal", "run_1")
    s.record_task("run_1", t)
    s.update_task_status("run_1", t.task_id, TaskStatus.RUNNING)
    assert s.current_run == "run_1"

    # Re-open from disk
    s2 = State(tmp_path)
    run = s2.get_run("run_1")
    assert run is not None
    assert run["tasks"][t.task_id]["status"] == "running"
    assert s2.current_run == "run_1"

    s2.finish_run("run_1")
    assert s2.current_run is None
    assert s2.get_run("run_1")["finished_at"] is not None
