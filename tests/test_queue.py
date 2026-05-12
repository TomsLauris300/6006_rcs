"""Tests for the file-based task queue and schema round-trips."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.queue import TaskQueue
from orchestrator.schema import AgentType, Result, Task, TaskStatus


def test_task_roundtrip():
    t = Task.new(AgentType.CODER, "do the thing", context={"file": "x.py"})
    raw = t.to_json()
    t2 = Task.from_json(raw)
    assert t2.task_id == t.task_id
    assert t2.agent_type == AgentType.CODER
    assert t2.status == TaskStatus.PENDING
    assert t2.context == {"file": "x.py"}


def test_enqueue_and_pending(tmp_path: Path):
    q = TaskQueue(tmp_path)
    t = Task.new(AgentType.CODER, "edit foo")
    q.enqueue(t)
    pending = q.pending()
    assert len(pending) == 1
    assert pending[0].task_id == t.task_id


def test_write_result_removes_task(tmp_path: Path):
    q = TaskQueue(tmp_path)
    t = Task.new(AgentType.CODER, "edit foo")
    q.enqueue(t)
    r = Result(
        task_id=t.task_id,
        status=TaskStatus.COMPLETED,
        output="done",
        agent_type=AgentType.CODER,
    )
    q.write_result(r)
    assert q.get_result(t.task_id).output == "done"
    assert not q.task_path(t.task_id).exists()
    assert q.pending() == []


def test_failed_result_written_to_errors(tmp_path: Path):
    q = TaskQueue(tmp_path)
    t = Task.new(AgentType.RESEARCHER, "look up X")
    q.enqueue(t)
    r = Result(
        task_id=t.task_id,
        status=TaskStatus.FAILED,
        output="",
        error="boom",
        exit_code=1,
        agent_type=AgentType.RESEARCHER,
    )
    q.write_result(r)
    assert q.error_path(t.task_id).exists()


def test_parse_plan_accepts_fenced_json():
    from orchestrator.hub import parse_plan

    output = """
    Here is the plan:

    ```json
    [
      {"agent_type": "coder", "instructions": "do A"},
      {"agent_type": "researcher", "instructions": "do B", "context": {"k": "v"}}
    ]
    ```
    """
    tasks = parse_plan(output, parent_id="task_parent")
    assert len(tasks) == 2
    assert tasks[0].agent_type == AgentType.CODER
    assert tasks[1].context == {"k": "v"}
    assert tasks[0].parent_id == "task_parent"


def test_parse_plan_accepts_raw_array():
    from orchestrator.hub import parse_plan

    raw = '[{"agent_type": "coder", "instructions": "x"}]'
    tasks = parse_plan(raw)
    assert len(tasks) == 1


def test_parse_plan_rejects_non_array():
    from orchestrator.hub import parse_plan

    with pytest.raises(ValueError):
        parse_plan('{"agent_type": "coder", "instructions": "x"}')
