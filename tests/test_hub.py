"""End-to-end test of the hub with a stubbed `claude` binary.

The stub script reads a prompt on stdin and echoes a canned response. This
exercises the full subprocess path (queue, agent runner, state, parallel
dispatch) without requiring a real Claude Code install.
"""

from __future__ import annotations

import os
import stat
import textwrap
from pathlib import Path

from orchestrator.agent import AgentConfig
from orchestrator.hub import OrchestratorHub
from orchestrator.schema import AgentType, Task, TaskStatus


def _write_stub(tmp_path: Path, *, exit_code: int = 0) -> Path:
    stub = tmp_path / "claude_stub.sh"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            # Consume stdin (the prompt), then emit a canned result block.
            cat > /dev/null
            cat <<'EOF'
            Did the work.

            ```result
            status: success
            summary: stub agent completed task
            ```
            EOF
            exit {exit_code}
            """
        )
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def test_dispatch_batch_runs_in_parallel(tmp_path: Path):
    stub = _write_stub(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    hub = OrchestratorHub(
        vault,
        max_workers=2,
        agent_config=AgentConfig(binary=str(stub), extra_args=()),
    )
    tasks = [
        Task.new(AgentType.CODER, "task A"),
        Task.new(AgentType.RESEARCHER, "task B"),
    ]
    results = hub.dispatch_batch(tasks, goal="test goal")
    assert len(results) == 2
    assert all(r.status == TaskStatus.COMPLETED for r in results)
    # Logs written
    for t in tasks:
        assert hub.queue.log_path(t.task_id).exists()
        assert hub.queue.result_path(t.task_id).exists()
    # Run state recorded and closed
    assert hub.state.current_run is None


def test_failed_exit_marks_failed(tmp_path: Path):
    stub = _write_stub(tmp_path, exit_code=2)
    vault = tmp_path / "vault"
    vault.mkdir()
    hub = OrchestratorHub(
        vault,
        max_workers=1,
        agent_config=AgentConfig(binary=str(stub), extra_args=()),
    )
    t = Task.new(AgentType.CODER, "will fail")
    results = hub.dispatch_batch([t])
    assert results[0].status == TaskStatus.FAILED
    assert hub.queue.error_path(t.task_id).exists()
