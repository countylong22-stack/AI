from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import json
import threading
from datetime import datetime, timezone


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    DESTRUCTIVE = "destructive"


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolPolicy:
    permission: Permission
    risk: Risk
    approval_required: bool = False


@dataclass(frozen=True)
class Action:
    tool: str
    reason: str
    action: str
    evidence: str
    risk: Risk
    target: str = ""


class EmergencyStop:
    def __init__(self) -> None:
        self._stopped = threading.Event()

    def stop(self) -> None:
        self._stopped.set()

    def reset(self) -> None:
        self._stopped.clear()

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def check(self) -> None:
        if self.stopped:
            raise RuntimeError("Rooster emergency stop is active.")


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, event: str, **data: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")


class RoosterGuard:
    """Policy enforcement layer between the agent and tools."""

    def __init__(self, workspace: Path, audit_path: Path) -> None:
        self.workspace = workspace.resolve()
        self.audit = AuditLog(audit_path)
        self.emergency_stop = EmergencyStop()
        self.policies: dict[str, ToolPolicy] = {
            "inspect_workspace": ToolPolicy(Permission.READ, Risk.LOW),
            "read_file": ToolPolicy(Permission.READ, Risk.LOW),
            "git_status": ToolPolicy(Permission.READ, Risk.LOW),
            "write_file": ToolPolicy(Permission.WRITE, Risk.MEDIUM, True),
            "run_tests": ToolPolicy(Permission.EXECUTE, Risk.MEDIUM, True),
            "git_commit": ToolPolicy(Permission.WRITE, Risk.HIGH, True),
            "git_push": ToolPolicy(Permission.NETWORK, Risk.CRITICAL, True),
            "delete_file": ToolPolicy(Permission.DESTRUCTIVE, Risk.CRITICAL, True),
        }
        self._approvals: set[str] = set()
        self._lock = threading.Lock()

    def approve(self, action_id: str) -> None:
        with self._lock:
            self._approvals.add(action_id)
        self.audit.write("approval_granted", action_id=action_id)

    def revoke_approval(self, action_id: str) -> None:
        with self._lock:
            self._approvals.discard(action_id)

    def action_id(self, action: Action) -> str:
        import hashlib
        raw = json.dumps(action.__dict__, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def authorize(self, action: Action) -> str:
        self.emergency_stop.check()
        policy = self.policies.get(action.tool)
        if policy is None:
            self.audit.write("action_denied", tool=action.tool, reason="unknown_tool")
            raise PermissionError(f"Tool is not registered with RoosterGuard: {action.tool}")
        if action.risk.value != policy.risk.value:
            raise PermissionError(f"Risk mismatch for {action.tool}: policy={policy.risk.value}")
        action_id = self.action_id(action)
        if policy.approval_required and action_id not in self._approvals:
            self.audit.write("approval_required", action_id=action_id, tool=action.tool, risk=action.risk.value, reason=action.reason)
            raise PermissionError(f"Human approval required for action {action_id}.")
        self.audit.write("action_authorized", action_id=action_id, tool=action.tool, reason=action.reason, action=action.action, evidence=action.evidence)
        return action_id

    def sandbox_path(self, relative_path: str) -> Path:
        candidate = (self.workspace / relative_path).resolve()
        sandbox = (self.workspace / ".rooster" / "sandbox").resolve()
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if sandbox not in candidate.parents and candidate != sandbox:
            raise PermissionError("Writes are restricted to the Rooster sandbox.")
        return candidate
