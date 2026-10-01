from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    checks: tuple[str, ...]
    evidence: dict[str, Any]


class VerificationEngine:
    """Verifies observable outcomes without claiming untested success."""

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
