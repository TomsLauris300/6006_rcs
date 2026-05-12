"""Logging setup for the orchestrator: timestamped console + per-run file log."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure(log_dir: Path | None = None, level: int = logging.INFO) -> Path | None:
    """Wire up root logger. Returns the path of the run log file, if any."""
    root = logging.getLogger()
    root.setLevel(level)
    # Clear any pre-existing handlers so repeated invocations don't duplicate.
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    if log_dir is None:
        return None
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"orchestrator-{int(time.time())}.log"
    fh = logging.FileHandler(path)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return path
