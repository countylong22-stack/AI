from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
from typing import Mapping, Sequence

from .guard import Action, Risk, RoosterGuard
from .runtime import RuntimeBudget


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CommandExecutor:
    """Execute only explicitly allowlisted, bounded commands inside the workspace."""

    DEFAULT_ALLOWED = frozenset({"python"})

    def __init__(
        self,
        guard: RoosterGuard,
        budget: RuntimeBudget | None = None,
        allowed_commands: set[str] | frozenset[str] | None = None,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 20000,
        allow_general_python: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be positive")
        self.guard = guard
        self.budget = budget
        self.allowed_commands = frozenset(
            allowed_commands if allowed_commands is not None else self.DEFAULT_ALLOWED
        )
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.allow_general_python = allow_general_python

    def _validate_arguments(self, command: Sequence[str]) -> None:
        """Apply executable-specific argument policy before approval/execution."""
        executable = Path(command[0]).name.lower()
        if executable != "python" or self.allow_general_python:
            return

        args = list(command[1:])
        if not args:
            raise PermissionError("Python requires the guarded unittest module in default mode.")
        if args[0] != "-m" or len(args) < 2 or args[1].lower() != "unittest":
            self.guard.audit.write(
                "command_denied",
                command=list(command),
                reason="python_arguments_not_allowlisted",
            )
            raise PermissionError(
                "Default Python policy permits only: python -m unittest ..."
            )
        forbidden_modules = {
            "socket", "http.server", "urllib", "urllib.request", "urllib3",
            "requests", "httpx", "ftplib", "smtplib", "imaplib", "poplib",
            "asyncio",
        }
        if len(args) >= 3 and args[2].lower() in forbidden_modules:
            self.guard.audit.write(
                "command_denied",
                command=list(command),
                reason="python_network_module_denied",
            )
            raise PermissionError(
                f"Python module is denied by default policy: {args[2]}"
            )

    def run(
        self,
        command: Sequence[str],
        *,
        reason: str,
        evidence: str,
        target: str = "",
    ) -> CommandResult:
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise ValueError("Command must be a non-empty sequence of non-empty strings.")
        executable = Path(command[0]).name.lower()
        if executable not in {name.lower() for name in self.allowed_commands}:
            self.guard.audit.write(
                "command_denied", command=list(command), reason="executable_not_allowlisted"
            )
            raise PermissionError(f"Command is not allowlisted: {command[0]}")

        self._validate_arguments(command)
        workspace = self.guard.workspace
        action = Action(
            "run_command",
            reason,
            f"Execute allowlisted command: {' '.join(command)}",
            evidence,
            Risk.MEDIUM,
            target,
        )
        self.guard.authorize(action)
        self.guard.emergency_stop.check()
        if self.budget is not None:
            self.budget.begin_step()

        env: Mapping[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "SystemRoot": os.environ.get("SystemRoot", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }
        self.guard.audit.write("command_started", command=list(command), target=target)
        try:
            completed = subprocess.run(
                list(command),
                cwd=workspace,
                env=dict(env),
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            result = CommandResult(
                tuple(command),
                completed.returncode,
                completed.stdout[: self.max_output_chars],
                completed.stderr[: self.max_output_chars],
            )
        except subprocess.TimeoutExpired as exc:
            if self.budget is not None:
                self.budget.record_failure()
            stdout = (exc.stdout or b"")[: self.max_output_chars]
            stderr = (exc.stderr or b"")[: self.max_output_chars]
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            result = CommandResult(tuple(command), -1, stdout, stderr, timed_out=True)
            self.guard.audit.write(
                "command_timeout", command=list(command), target=target
            )
            return result
        except Exception as exc:
            if self.budget is not None:
                self.budget.record_failure()
            self.guard.audit.write(
                "command_failed", command=list(command), target=target, error=str(exc)
            )
            raise

        self.guard.audit.write(
            "command_completed",
            command=list(command),
            target=target,
            returncode=result.returncode,
            timed_out=False,
            stdout_chars=len(result.stdout),
            stderr_chars=len(result.stderr),
        )
        return result
