"""
Command Executor.
Executes terminal commands to build and run applications.
Handles command execution, output capture, timeouts, and process management.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("autodev")


@dataclass
class CommandResult:
    """Result of a command execution."""

    command: list[str] | str
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    success: bool = False
    timed_out: bool = False
    duration_seconds: float = 0.0


class CommandExecutor:
    """Executes terminal commands with output capture and timeout support."""

    def __init__(self, default_timeout: int = 60, env: dict[str, str] | None = None) -> None:
        """
        Initialize the command executor.

        Args:
            default_timeout: Default timeout in seconds for commands.
            env: Additional environment variables.
        """
        self.default_timeout = default_timeout
        self._env = os.environ.copy()
        if env:
            self._env.update(env)
        self._running_processes: list[asyncio.subprocess.Process] = []

    async def run(
        self,
        command: list[str] | str,
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """
        Execute a command and return the result.

        Args:
            command: Command to execute (list or string).
            cwd: Working directory.
            timeout: Timeout in seconds.
            env: Additional environment variables for this command.

        Returns:
            CommandResult with output and status.
        """
        import time

        cmd_timeout = timeout or self.default_timeout
        cmd_env = self._env.copy()
        if env:
            cmd_env.update(env)

        cmd_str = command if isinstance(command, str) else " ".join(command)
        logger.info("Executing: %s (timeout=%ds, cwd=%s)", cmd_str, cmd_timeout, cwd)

        start = time.time()

        try:
            if isinstance(command, str):
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=cmd_env,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=cmd_env,
                )

            self._running_processes.append(process)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=cmd_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration = time.time() - start
                logger.warning("Command timed out after %ds: %s", cmd_timeout, cmd_str)
                return CommandResult(
                    command=command,
                    stdout="",
                    stderr=f"Command timed out after {cmd_timeout}s",
                    return_code=-1,
                    success=False,
                    timed_out=True,
                    duration_seconds=duration,
                )
            finally:
                if process in self._running_processes:
                    self._running_processes.remove(process)

            duration = time.time() - start
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""
            return_code = process.returncode or 0
            success = return_code == 0

            if success:
                logger.info("Command succeeded (%.1fs): %s", duration, cmd_str)
            else:
                logger.warning(
                    "Command failed (code=%d, %.1fs): %s\nStderr: %s",
                    return_code, duration, cmd_str, stderr_str[:500],
                )

            return CommandResult(
                command=command,
                stdout=stdout_str,
                stderr=stderr_str,
                return_code=return_code,
                success=success,
                timed_out=False,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            duration = time.time() - start
            logger.error("Command not found: %s", cmd_str)
            return CommandResult(
                command=command,
                stderr=f"Command not found: {cmd_str}",
                return_code=127,
                success=False,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start
            logger.error("Command execution error: %s", str(e))
            return CommandResult(
                command=command,
                stderr=str(e),
                return_code=-1,
                success=False,
                duration_seconds=duration,
            )

    async def run_background(
        self,
        command: list[str] | str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> asyncio.subprocess.Process:
        """
        Start a command in the background (e.g., dev servers).

        Args:
            command: Command to execute.
            cwd: Working directory.
            env: Additional environment variables.

        Returns:
            The running subprocess.Process.
        """
        cmd_env = self._env.copy()
        if env:
            cmd_env.update(env)

        cmd_str = command if isinstance(command, str) else " ".join(command)
        logger.info("Starting background process: %s", cmd_str)

        if isinstance(command, str):
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env,
            )

        self._running_processes.append(process)
        logger.info("Background process started (PID=%d): %s", process.pid, cmd_str)
        return process

    async def stop_background(self, process: asyncio.subprocess.Process) -> None:
        """
        Stop a background process gracefully.

        Args:
            process: The process to stop.
        """
        if process.returncode is not None:
            logger.info("Process already terminated (PID=%d)", process.pid)
            return

        logger.info("Stopping background process (PID=%d)", process.pid)
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Force killing process (PID=%d)", process.pid)
            process.kill()
            await process.wait()

        if process in self._running_processes:
            self._running_processes.remove(process)

    async def stop_all(self) -> None:
        """Stop all running background processes."""
        for process in list(self._running_processes):
            await self.stop_background(process)

    async def read_process_output(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 5.0,
    ) -> tuple[str, str]:
        """
        Read available output from a running process.

        Args:
            process: The running process.
            timeout: How long to wait for output.

        Returns:
            Tuple of (stdout, stderr) collected so far.
        """
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def _read_stream(
            stream: asyncio.StreamReader | None,
            chunks: list[str],
        ) -> None:
            if stream is None:
                return
            try:
                while True:
                    line = await asyncio.wait_for(stream.readline(), timeout=0.5)
                    if not line:
                        break
                    chunks.append(line.decode("utf-8", errors="replace"))
            except asyncio.TimeoutError:
                pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(process.stdout, stdout_chunks),
                    _read_stream(process.stderr, stderr_chunks),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass

        return "".join(stdout_chunks), "".join(stderr_chunks)
