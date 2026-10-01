from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING
import os
import subprocess
import sys

if TYPE_CHECKING:
    from .guard import RoosterGuard


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    checks: tuple[str, ...]
    evidence: dict[str, Any]


class VerificationEngine:
    """Verifies observable outcomes without claiming untested success."""

    TEST_COMMAND = (
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    )
    TEST_TIMEOUT_SECONDS = 60.0
    MAX_OUTPUT_CHARS = 20000

    def verify_checkpoint(self, path: Path) -> VerificationResult:
        exists = path.exists() and path.is_dir()
        return VerificationResult(
            success=exists,
            checks=("checkpoint_exists",),
            evidence={"checkpoint": str(path), "exists": exists},
        )

    def verify_task_observation(
        self, workspace_items: list[dict[str, Any]], git_status: str
    ) -> VerificationResult:
        inventory_valid = isinstance(workspace_items, list)
        status_valid = isinstance(git_status, str)
        return VerificationResult(
            success=inventory_valid and status_valid,
            checks=("workspace_inventory_captured", "git_status_captured"),
            evidence={
                "workspace_item_count": len(workspace_items)
                if inventory_valid
                else None,
                "git_status": git_status,
            },
        )

    def run_test_suite(
        self,
        workspace: Path,
        guard: RoosterGuard,
        *,
        timeout_seconds: float = TEST_TIMEOUT_SECONDS,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ) -> VerificationResult:
        """Run only the fixed repository unittest suite under a guarded boundary."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be positive")

        command = list(self.TEST_COMMAND)
        guard.emergency_stop.check()
        guard.audit.write(
            "test_suite_started",
            command=command,
            target="tests",
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
        )

        env = {
            "PATH": os.environ.get("PATH", ""),
            "SystemRoot": os.environ.get("SystemRoot", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }

        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=env,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout[:max_output_chars]
            stderr = completed.stderr[:max_output_chars]
            success = completed.returncode == 0
            evidence = {
                "command": command,
                "returncode": completed.returncode,
                "timed_out": False,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_chars": len(stdout),
                "stderr_chars": len(stderr),
                "timeout_seconds": timeout_seconds,
                "max_output_chars": max_output_chars,
            }
            guard.audit.write(
                "test_suite_completed",
                command=command,
                target="tests",
                returncode=completed.returncode,
                timed_out=False,
                stdout_chars=len(stdout),
                stderr_chars=len(stderr),
            )
            return VerificationResult(
                success=success,
                checks=("test_suite_executed", "test_suite_exit_status"),
                evidence=evidence,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            stdout = stdout[:max_output_chars]
            stderr = stderr[:max_output_chars]
            evidence = {
                "command": command,
                "returncode": -1,
                "timed_out": True,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_chars": len(stdout),
                "stderr_chars": len(stderr),
                "timeout_seconds": timeout_seconds,
                "max_output_chars": max_output_chars,
            }
            guard.audit.write(
                "test_suite_timeout",
                command=command,
                target="tests",
                timeout_seconds=timeout_seconds,
                stdout_chars=len(stdout),
                stderr_chars=len(stderr),
            )
            return VerificationResult(
                success=False,
                checks=("test_suite_executed", "test_suite_timeout"),
                evidence=evidence,
            )
        except Exception as exc:
            guard.audit.write(
                "test_suite_failed_to_start",
                command=command,
                target="tests",
                error=str(exc),
            )
            raise
