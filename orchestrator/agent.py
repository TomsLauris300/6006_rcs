"""Subprocess runner that invokes `claude --print` to execute a task.

The runner is intentionally thin: it builds a self-contained prompt from the
task plus the agent's system prompt, spawns Claude Code headlessly, captures
stdout/stderr, and returns a `Result`. The orchestrator decides what to do
with the result.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .schema import AgentType, Result, Task, TaskStatus

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class AgentConfig:
    binary: str = "claude"
    extra_args: tuple[str, ...] = ("--dangerously-skip-permissions",)
    timeout_s: int = 60 * 30  # 30 minutes
    cwd: Path | None = None


def load_system_prompt(agent_type: AgentType) -> str:
    path = PROMPTS_DIR / f"{agent_type.value}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt for agent type {agent_type!r}: {path}")
    return path.read_text()


def build_prompt(task: Task, vault_root: Path) -> str:
    system_prompt = load_system_prompt(task.agent_type)
    ctx_lines = [f"- {k}: {v}" for k, v in task.context.items()]
    ctx = "\n".join(ctx_lines) if ctx_lines else "(no extra context)"
    return (
        f"{system_prompt}\n\n"
        f"---\n"
        f"# Task\n"
        f"task_id: {task.task_id}\n"
        f"vault_root: {vault_root}\n"
        f"expected_output_format: {task.expected_output_format}\n\n"
        f"## Context\n{ctx}\n\n"
        f"## Instructions\n{task.instructions}\n"
    )


class AgentRunner:
    def __init__(self, vault_root: Path | str, config: AgentConfig | None = None):
        self.vault_root = Path(vault_root).expanduser().resolve()
        self.config = config or AgentConfig()
        if self.config.cwd is None:
            self.config.cwd = self.vault_root

    def _binary_path(self) -> str:
        path = shutil.which(self.config.binary)
        if not path:
            raise FileNotFoundError(
                f"`{self.config.binary}` not found on PATH. "
                "Install Claude Code or set AgentConfig.binary."
            )
        return path

    def run(self, task: Task, log_path: Path | None = None) -> Result:
        prompt = build_prompt(task, self.vault_root)
        cmd = [self._binary_path(), "--print", *self.config.extra_args]
        started = time.time()
        log.info("spawning agent task_id=%s agent=%s", task.task_id, task.agent_type.value)
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(self.config.cwd),
                timeout=self.config.timeout_s,
                env=os.environ.copy(),
                check=False,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            exit_code = 124
        finished = time.time()

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"$ {' '.join(cmd)}\n\n"
                f"--- prompt ---\n{prompt}\n\n"
                f"--- stdout (exit={exit_code}) ---\n{stdout}\n\n"
                f"--- stderr ---\n{stderr}\n"
            )

        status = TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
        return Result(
            task_id=task.task_id,
            status=status,
            output=stdout.strip(),
            error=stderr.strip() or None if status == TaskStatus.FAILED else None,
            exit_code=exit_code,
            started_at=started,
            finished_at=finished,
            agent_type=task.agent_type,
        )
