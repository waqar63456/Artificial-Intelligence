"""
Logging and action tracking system for the autonomous development platform.
Tracks all agent actions, decisions, and outcomes for self-improvement.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ActionRecord:
    """Record of a single agent action."""

    timestamp: str
    agent: str
    action: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""
    duration_seconds: float = 0.0


class ActionTracker:
    """Tracks all agent actions for logging and self-improvement."""

    def __init__(self, log_dir: str = "./logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.actions: list[ActionRecord] = []
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._session_file = self.log_dir / f"session_{self._session_id}.jsonl"

    def record(
        self,
        agent: str,
        action: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        success: bool = True,
        error: str = "",
        duration_seconds: float = 0.0,
    ) -> ActionRecord:
        """Record an agent action."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            action=action,
            input_data=input_data or {},
            output_data=output_data or {},
            success=success,
            error=error,
            duration_seconds=duration_seconds,
        )
        self.actions.append(record)
        self._persist(record)
        return record

    def _persist(self, record: ActionRecord) -> None:
        """Persist a record to the session log file."""
        with open(self._session_file, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def get_error_history(self) -> list[ActionRecord]:
        """Get all failed actions."""
        return [a for a in self.actions if not a.success]

    def get_agent_history(self, agent: str) -> list[ActionRecord]:
        """Get all actions by a specific agent."""
        return [a for a in self.actions if a.agent == agent]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all tracked actions."""
        total = len(self.actions)
        successes = sum(1 for a in self.actions if a.success)
        failures = total - successes
        agents = set(a.agent for a in self.actions)
        return {
            "session_id": self._session_id,
            "total_actions": total,
            "successes": successes,
            "failures": failures,
            "agents_involved": sorted(agents),
            "total_duration": sum(a.duration_seconds for a in self.actions),
        }


def setup_logging(log_dir: str = "./logs", verbose: bool = False) -> logging.Logger:
    """Set up the platform logger."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("autodev")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    ch.setFormatter(ch_format)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_path / "autodev.log")
    fh.setLevel(logging.DEBUG)
    fh_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s"
    )
    fh.setFormatter(fh_format)
    logger.addHandler(fh)

    return logger


class TimedOperation:
    """Context manager for timing operations."""

    def __init__(self, tracker: ActionTracker, agent: str, action: str) -> None:
        self.tracker = tracker
        self.agent = agent
        self.action = action
        self._start: float = 0.0
        self._input_data: dict[str, Any] = {}
        self._output_data: dict[str, Any] = {}

    def set_input(self, data: dict[str, Any]) -> None:
        self._input_data = data

    def set_output(self, data: dict[str, Any]) -> None:
        self._output_data = data

    def __enter__(self) -> TimedOperation:
        self._start = time.time()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        duration = time.time() - self._start
        success = exc_type is None
        error = str(exc_val) if exc_val else ""
        self.tracker.record(
            agent=self.agent,
            action=self.action,
            input_data=self._input_data,
            output_data=self._output_data,
            success=success,
            error=error,
            duration_seconds=duration,
        )
