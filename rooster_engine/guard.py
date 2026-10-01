from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone


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


@dataclass(frozen=True)
class Approval:
    action_id: str
    expires_at: datetime
    actor: str = "human"
    task_id: str = ""
    granted_at: datetime = datetime.min.replace(tzinfo=timezone.utc)


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
    """Thread-safe JSONL audit log with a tamper-evident hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._previous_hash = self._load_previous_hash()

    def _load_previous_hash(self) -> str:
        if not self.path.exists():
            return ""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return ""
            return str(json.loads(lines[-1]).get("record_hash", ""))
        except (OSError, ValueError, TypeError):
            return ""

    def write(self, event: str, **data: Any) -> None:
        with self._lock:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **data,
                "previous_hash": self._previous_hash,
            }
            payload = json.dumps(
                record, sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
            record["record_hash"] = hashlib.sha256(payload).hexdigest()
            self._previous_hash = record["record_hash"]
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


class RoosterGuard:
    """Policy enforcement layer between the agent and tools."""

    DEFAULT_APPROVAL_TTL = timedelta(minutes=10)

    def __init__(self, workspace: Path, audit_path: Path) -> None:
        self.workspace = workspace.resolve()
        self.audit = AuditLog(audit_path)
        self.emergency_stop = EmergencyStop()
        self.policies: dict[str, ToolPolicy] = {
            "inspect_workspace": ToolPolicy(Permission.READ, Risk.LOW),
            "read_file": ToolPolicy(Permission.READ, Risk.LOW),
            "git_status": ToolPolicy(Permission.READ, Risk.LOW),
            "checkpoint": ToolPolicy(Permission.READ, Risk.LOW),
            "write_file": ToolPolicy(Permission.WRITE, Risk.MEDIUM, True),
            "run_tests": ToolPolicy(Permission.EXECUTE, Risk.MEDIUM, True),
            "run_command": ToolPolicy(Permission.EXECUTE, Risk.MEDIUM, True),
            "git_commit": ToolPolicy(Permission.WRITE, Risk.HIGH, True),
            "git_push": ToolPolicy(Permission.NETWORK, Risk.CRITICAL, True),
            "delete_file": ToolPolicy(Permission.DESTRUCTIVE, Risk.CRITICAL, True),
        }
        self._approvals: dict[str, Approval] = {}
        self._lock = threading.Lock()

    def approve(
        self,
        action_id: str,
        ttl: timedelta | None = None,
        *,
        actor: str = "human",
        task_id: str = "",
    ) -> None:
        if not action_id:
            raise ValueError("Approval requires a non-empty action ID.")
        if not actor:
            raise ValueError("Approval actor must be non-empty.")
        if not isinstance(task_id, str):
            raise ValueError("Approval task ID must be a string.")
        granted_at = datetime.now(timezone.utc)
        expires_at = granted_at + (ttl or self.DEFAULT_APPROVAL_TTL)
        with self._lock:
            self._approvals[action_id] = Approval(
                action_id, expires_at, actor, task_id, granted_at
            )
        self.audit.write(
            "approval_granted",
            action_id=action_id,
            actor=actor,
            task_id=task_id,
            granted_at=granted_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

    def revoke_approval(self, action_id: str) -> None:
        with self._lock:
            self._approvals.pop(action_id, None)
        self.audit.write("approval_revoked", action_id=action_id)

    def action_id(self, action: Action) -> str:
        raw = json.dumps(action.__dict__, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def authorize(
        self,
        action: Action,
        *,
        actor: str = "human",
        task_id: str = "",
    ) -> str:
        self.emergency_stop.check()
        if not actor:
            raise ValueError("Authorization actor must be non-empty.")
        if not isinstance(task_id, str):
            raise ValueError("Authorization task ID must be a string.")
        policy = self.policies.get(action.tool)
        if policy is None:
            self.audit.write(
                "action_denied", tool=action.tool, reason="unknown_tool"
            )
            raise PermissionError(
                f"Tool is not registered with RoosterGuard: {action.tool}"
            )
        if action.risk != policy.risk:
            self.audit.write(
                "action_denied",
                tool=action.tool,
                reason="risk_mismatch",
                requested_risk=action.risk.value,
                policy_risk=policy.risk.value,
            )
            raise PermissionError(
                f"Risk mismatch for {action.tool}: policy={policy.risk.value}"
            )

        if action.tool == "write_file" and action.target:
            self.enforce_write_target(action.target)

        action_id = self.action_id(action)
        if policy.approval_required:
            with self._lock:
                approval = self._approvals.get(action_id)
                if approval is not None and approval.expires_at <= datetime.now(timezone.utc):
                    self._approvals.pop(action_id, None)
                    approval = None
                if approval is None:
                    approved = False
                elif approval.actor != actor or approval.task_id != task_id:
                    self.audit.write(
                        "approval_denied",
                        action_id=action_id,
                        tool=action.tool,
                        reason="approval_context_mismatch",
                        approval_actor=approval.actor,
                        requested_actor=actor,
                        approval_task_id=approval.task_id,
                        requested_task_id=task_id,
                    )
                    approved = False
                else:
                    self._approvals.pop(action_id, None)
                    approved = True

            if not approved:
                self.audit.write(
                    "approval_required",
                    action_id=action_id,
                    tool=action.tool,
                    risk=action.risk.value,
                    reason=action.reason,
                    actor=actor,
                    task_id=task_id,
                )
                raise PermissionError(
                    f"Human approval required for action {action_id}."
                )
            self.audit.write(
                "approval_consumed",
                action_id=action_id,
                tool=action.tool,
                actor=actor,
                task_id=task_id
            )

        self.audit.write(
            "action_authorized",
            action_id=action_id,
            tool=action.tool,
            reason=action.reason,
            action=action.action,
            evidence=action.evidence,
            risk=action.risk.value,
            target=action.target,
        )
        return action_id

    PROTECTED_PATHS = (
        "rooster_engine/guard.py",
        "rooster_engine/core.py",
        "rooster_engine/command.py",
        "rooster_engine/runtime.py",
        "rooster_engine/verification.py",
        "rooster_engine/analysis.py",
        "app.py",
        ".github/workflows/*",
        "SECURITY.md",
    )

    def protected_path(self, relative_path: str) -> str | None:
        """Return the protected rule matching a workspace-relative path, if any."""
        candidate = Path(relative_path.replace("\\\\", "/"))
        if candidate.is_absolute() or not relative_path:
            return None
        normalized = candidate.as_posix()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        for rule in self.PROTECTED_PATHS:
            if rule.endswith("/*"):
                prefix = rule[:-2].rstrip("/") + "/"
                if normalized.lower().startswith(prefix.lower()):
                    return rule
            elif normalized.lower() == rule.lower():
                return rule
        return None

    def enforce_write_target(self, relative_path: str) -> None:
        """Block autonomous writes to security-critical workspace paths."""
        rule = self.protected_path(relative_path)
        if rule is not None:
            self.audit.write(
                "protected_write_denied",
                target=relative_path,
                rule=rule,
                reason="protected_system_file",
            )
            raise PermissionError(
                f"Write target is protected by RoosterGuard: {relative_path}"
            )

    def sandbox_path(self, relative_path: str) -> Path:
        sandbox = (self.workspace / ".rooster" / "sandbox").resolve()
        candidate = sandbox / relative_path
        try:
            candidate.relative_to(sandbox)
        except ValueError as exc:
            raise PermissionError(
                "Writes are restricted to the Rooster sandbox."
            ) from exc

        # Resolve the existing path and parents to catch symlink escapes.
        resolved = candidate.resolve(strict=False)
        if sandbox not in resolved.parents and resolved != sandbox:
            raise PermissionError("Writes are restricted to the Rooster sandbox.")

        return resolved
