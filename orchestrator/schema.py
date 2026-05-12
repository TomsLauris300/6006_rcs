"""Message schema for tasks and results exchanged via the file-based queue."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    CODER = "coder"
    RESEARCHER = "researcher"
    PLANNER = "planner"


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class Task:
    task_id: str
    agent_type: AgentType
    instructions: str
    context: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=_now)
    parent_id: str | None = None
    expected_output_format: str = "markdown"

    @classmethod
    def new(
        cls,
        agent_type: AgentType | str,
        instructions: str,
        context: dict[str, Any] | None = None,
        parent_id: str | None = None,
        expected_output_format: str = "markdown",
    ) -> "Task":
        return cls(
            task_id=_new_id("task"),
            agent_type=AgentType(agent_type),
            instructions=instructions,
            context=context or {},
            parent_id=parent_id,
            expected_output_format=expected_output_format,
        )

    def to_json(self) -> str:
        data = asdict(self)
        data["agent_type"] = self.agent_type.value
        data["status"] = self.status.value
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "Task":
        data = json.loads(raw)
        data["agent_type"] = AgentType(data["agent_type"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> "Task":
        return cls.from_json(path.read_text())


@dataclass
class Result:
    task_id: str
    status: TaskStatus
    output: str = ""
    error: str | None = None
    exit_code: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    agent_type: AgentType = AgentType.CODER

    @property
    def duration_s(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_json(self) -> str:
        data = asdict(self)
        data["agent_type"] = self.agent_type.value
        data["status"] = self.status.value
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "Result":
        data = json.loads(raw)
        data["agent_type"] = AgentType(data["agent_type"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> "Result":
        return cls.from_json(path.read_text())
