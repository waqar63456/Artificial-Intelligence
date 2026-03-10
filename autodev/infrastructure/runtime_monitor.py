"""
Runtime Monitor.
Monitors runtime logs and detects errors from terminal output,
build tools, and server logs. Provides real-time error detection.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("autodev")


class ErrorSeverity(Enum):
    """Severity levels for detected errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DetectedError:
    """A detected runtime error."""

    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    source: str = ""  # "terminal", "build", "server", "browser"
    file_path: str = ""
    line_number: int = 0
    column_number: int = 0
    stack_trace: str = ""
    raw_output: str = ""


# Common error patterns for different technologies
ERROR_PATTERNS: list[tuple[str, ErrorSeverity, str]] = [
    # Node.js / JavaScript
    (r"Error:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"TypeError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"ReferenceError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"SyntaxError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"Cannot find module\s+'(.+)'", ErrorSeverity.ERROR, "dependency"),
    (r"ENOENT:\s+(.+)", ErrorSeverity.ERROR, "filesystem"),
    (r"EADDRINUSE:\s+(.+)", ErrorSeverity.ERROR, "network"),
    (r"npm ERR!\s+(.+)", ErrorSeverity.ERROR, "build"),
    (r"npm warn\s+(.+)", ErrorSeverity.WARNING, "build"),

    # Python
    (r"Traceback \(most recent call last\)", ErrorSeverity.ERROR, "runtime"),
    (r"ModuleNotFoundError:\s+(.+)", ErrorSeverity.ERROR, "dependency"),
    (r"ImportError:\s+(.+)", ErrorSeverity.ERROR, "dependency"),
    (r"IndentationError:\s+(.+)", ErrorSeverity.ERROR, "syntax"),
    (r"NameError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"AttributeError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"ValueError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),
    (r"KeyError:\s+(.+)", ErrorSeverity.ERROR, "runtime"),

    # PHP / Laravel
    (r"PHP Fatal error:\s+(.+)", ErrorSeverity.CRITICAL, "runtime"),
    (r"PHP Warning:\s+(.+)", ErrorSeverity.WARNING, "runtime"),
    (r"SQLSTATE\[(.+?)\]", ErrorSeverity.ERROR, "database"),

    # General
    (r"FATAL:\s+(.+)", ErrorSeverity.CRITICAL, "runtime"),
    (r"CRITICAL:\s+(.+)", ErrorSeverity.CRITICAL, "runtime"),
    (r"failed with exit code\s+(\d+)", ErrorSeverity.ERROR, "build"),
    (r"permission denied", ErrorSeverity.ERROR, "filesystem"),
    (r"connection refused", ErrorSeverity.ERROR, "network"),
    (r"out of memory", ErrorSeverity.CRITICAL, "system"),
]

# File path extraction patterns
FILE_PATH_PATTERNS = [
    # Node.js stack trace: at Object.<anonymous> (/path/to/file.js:10:5)
    r"at\s+.+\s+\((.+?):(\d+):(\d+)\)",
    # Python: File "/path/to/file.py", line 10
    r'File "(.+?)", line (\d+)',
    # General: /path/to/file.ext:10:5
    r"([/\\][\w/\\.\\-]+\.\w+):(\d+)(?::(\d+))?",
    # Webpack/Vite style: ./src/App.tsx:10:5
    r"(\.\/[\w/\\.\\-]+\.\w+):(\d+)(?::(\d+))?",
]


class RuntimeMonitor:
    """Monitors application runtime for errors."""

    def __init__(self) -> None:
        self.detected_errors: list[DetectedError] = []
        self._error_patterns = [
            (re.compile(pattern, re.IGNORECASE), severity, source)
            for pattern, severity, source in ERROR_PATTERNS
        ]
        self._file_patterns = [re.compile(p) for p in FILE_PATH_PATTERNS]

    def analyze_output(self, output: str, source: str = "terminal") -> list[DetectedError]:
        """
        Analyze command output for errors.

        Args:
            output: The raw output text to analyze.
            source: Source of the output (terminal, build, server).

        Returns:
            List of detected errors.
        """
        errors: list[DetectedError] = []
        lines = output.split("\n")

        for i, line in enumerate(lines):
            for pattern, severity, error_source in self._error_patterns:
                match = pattern.search(line)
                if match:
                    # Extract file path info if available
                    file_path, line_num, col_num = self._extract_file_info(
                        "\n".join(lines[max(0, i - 2):i + 5])
                    )

                    # Build stack trace from surrounding lines
                    stack_start = max(0, i - 2)
                    stack_end = min(len(lines), i + 10)
                    stack_trace = "\n".join(lines[stack_start:stack_end])

                    error = DetectedError(
                        message=match.group(0),
                        severity=severity,
                        source=source,
                        file_path=file_path,
                        line_number=line_num,
                        column_number=col_num,
                        stack_trace=stack_trace,
                        raw_output=line,
                    )
                    errors.append(error)
                    break  # Only match one pattern per line

        self.detected_errors.extend(errors)
        if errors:
            logger.warning(
                "Detected %d errors in %s output", len(errors), source
            )
        return errors

    def _extract_file_info(self, text: str) -> tuple[str, int, int]:
        """
        Extract file path, line, and column from error text.

        Returns:
            Tuple of (file_path, line_number, column_number).
        """
        for pattern in self._file_patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                file_path = groups[0] if len(groups) > 0 else ""
                line_num = int(groups[1]) if len(groups) > 1 and groups[1] else 0
                col_num = int(groups[2]) if len(groups) > 2 and groups[2] else 0
                return file_path, line_num, col_num
        return "", 0, 0

    async def monitor_process(
        self,
        process: asyncio.subprocess.Process,
        source: str = "server",
        duration: float = 10.0,
    ) -> list[DetectedError]:
        """
        Monitor a running process for errors over a duration.

        Args:
            process: The running process to monitor.
            source: Label for the error source.
            duration: How long to monitor in seconds.

        Returns:
            List of errors detected during monitoring.
        """
        logger.info("Monitoring process (PID=%d) for %.1fs", process.pid, duration)
        all_errors: list[DetectedError] = []
        collected_output = ""

        try:
            end_time = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < end_time:
                if process.returncode is not None:
                    # Process has exited
                    break

                # Try to read output
                if process.stdout:
                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(), timeout=1.0
                        )
                        if line:
                            decoded = line.decode("utf-8", errors="replace")
                            collected_output += decoded
                            errors = self.analyze_output(decoded, source)
                            all_errors.extend(errors)
                    except asyncio.TimeoutError:
                        pass

                if process.stderr:
                    try:
                        line = await asyncio.wait_for(
                            process.stderr.readline(), timeout=0.5
                        )
                        if line:
                            decoded = line.decode("utf-8", errors="replace")
                            collected_output += decoded
                            errors = self.analyze_output(decoded, source)
                            all_errors.extend(errors)
                    except asyncio.TimeoutError:
                        pass

        except Exception as e:
            logger.error("Error during process monitoring: %s", str(e))

        return all_errors

    def get_critical_errors(self) -> list[DetectedError]:
        """Get all critical and error-level errors."""
        return [
            e for e in self.detected_errors
            if e.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.ERROR)
        ]

    def get_errors_for_file(self, file_path: str) -> list[DetectedError]:
        """Get all errors related to a specific file."""
        return [
            e for e in self.detected_errors
            if file_path in e.file_path
        ]

    def clear(self) -> None:
        """Clear all detected errors."""
        self.detected_errors.clear()

    def get_error_summary(self) -> str:
        """Get a summary of all detected errors."""
        if not self.detected_errors:
            return "No errors detected."

        summary_parts = [f"Total errors: {len(self.detected_errors)}"]
        by_severity: dict[str, int] = {}
        for e in self.detected_errors:
            by_severity[e.severity.value] = by_severity.get(e.severity.value, 0) + 1

        for severity, count in sorted(by_severity.items()):
            summary_parts.append(f"  {severity}: {count}")

        return "\n".join(summary_parts)
