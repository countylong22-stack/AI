from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Any
import json
import shutil
import subprocess
from datetime import datetime

from .guard import Action, Risk, RoosterGuard


@dataclass
class Task:
    objective: str
    status: str = "queued"
    created: str = ""
    completed: str = ""
    result: str = ""
    reason: str = ""
    evidence: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat(timespec="seconds")


class ToolRegistry:
    def __init__(self, guard: RoosterGuard):
        self._tools: dict[str, Callable[..., Any]] = {}
        self.guard = guard

    def register(self, name: str, function: Callable[..., Any]) -> None:
        self._tools[name] = function

    def names(self) -> list[str]:
        return sorted(self._tools)

    def run(self, name: str, *args, reason: str = "Tool requested by engineering task", action: str = "Execute tool", evidence: str = "Tool result", risk: Risk = Risk.LOW, target: str = "", **kwargs) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        self.guard.authorize(Action(name, reason, action, evidence, risk, target))
        self.guard.emergency_stop.check()
        self.guard.audit.write("action_started", tool=name, target=target)
        try:
            result = self._tools[name](*args, **kwargs)
            self.guard.audit.write("action_completed", tool=name, target=target, result_summary=str(result)[:500])
            return result
        except Exception as exc:
            self.guard.audit.write("action_failed", tool=name, target=target, error=str(exc))
            raise


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.rooster_dir = self.root / ".rooster"
        self.sandbox = self.rooster_dir / "sandbox"
        self.checkpoints = self.rooster_dir / "checkpoints"
        self.rooster_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.checkpoints.mkdir(parents=True, exist_ok=True)

    def inspect(self, limit: int = 100) -> list[dict[str, Any]]:
        items = []
        for path in sorted(self.root.iterdir(), key=lambda p: p.name.lower()):
            if path.name == ".rooster":
                continue
            items.append({"name": path.name, "type": "directory" if path.is_dir() else "file", "path": str(path)})
            if len(items) >= limit:
                break
        return items

    def read_text(self, relative_path: str, max_chars: int = 50000) -> str:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Path escapes workspace.")
        return path.read_text(encoding="utf-8")[:max_chars]

    def git_status(self) -> str:
        result = subprocess.run(["git", "status", "--short"], cwd=self.root, capture_output=True, text=True, timeout=60)
        return (result.stdout + result.stderr).strip()

    def write_sandbox(self, relative_path: str, content: str) -> str:
        path = self.sandbox / relative_path
        path = path.resolve()
        if self.sandbox.resolve() not in path.parents:
            raise ValueError("Sandbox path escapes .rooster/sandbox.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def checkpoint(self, label: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label).strip("_") or "checkpoint"
        target = self.checkpoints / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}"
        if target.exists():
            target = target.with_name(target.name + "_1")
        shutil.copytree(self.root, target, ignore=shutil.ignore_patterns(".git", ".rooster", "__pycache__", "*.pyc"))
        return target


class TaskStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            return [Task(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    def save(self, tasks: list[Task]) -> None:
        self.path.write_text(json.dumps([asdict(task) for task in tasks], indent=2), encoding="utf-8")


class AutonomousEngineer:
    def __init__(self, workspace: str | Path, memory_file: str | Path):
        self.workspace = Workspace(workspace)
        self.store = TaskStore(memory_file)
        self.tasks = self.store.load()
        self.guard = RoosterGuard(self.workspace.root, self.workspace.rooster_dir / "audit.jsonl")
        self.tools = ToolRegistry(self.guard)
        self._register_tools()

    def _register_tools(self) -> None:
        self.tools.register("inspect_workspace", self.workspace.inspect)
        self.tools.register("git_status", self.workspace.git_status)
        self.tools.register("read_file", self.workspace.read_text)
        self.tools.register("write_file", self.workspace.write_sandbox)
        self.tools.register("checkpoint", self.workspace.checkpoint)

    def plan(self, objective: str) -> list[str]:
        return [
            "Define the objective and evidence required for success",
            "Inspect the workspace without modifying project files",
            "Create a checkpoint before approved changes",
            "Make changes only through the guarded sandbox",
            "Verify the result and record evidence",
        ]

    def reason_action_evidence(self, objective: str) -> dict[str, str]:
        return {
            "reason": f"Advance the engineering objective: {objective}",
            "action": "Inspect, plan, checkpoint, then perform only authorized tool actions",
            "evidence": "Tool results, tests/checks, checkpoint path, and audit events",
        }

    def emergency_stop(self) -> None:
        self.guard.emergency_stop.stop()
        self.guard.audit.write("emergency_stop", source="operator")

    def reset_emergency_stop(self) -> None:
        self.guard.emergency_stop.reset()
        self.guard.audit.write("emergency_stop_reset", source="operator")

    def create_checkpoint(self, label: str = "pre_change") -> Path:
        path = self.tools.run("checkpoint", label, reason="Protect the current workspace before further work", action="Create recovery checkpoint", evidence="Checkpoint directory exists", risk=Risk.LOW, target=label)
        self.guard.audit.write("checkpoint_created", path=str(path), label=label)
        return path

    def run(self, objective: str) -> Task:
        task = Task(objective=objective, status="running")
        rationale = self.reason_action_evidence(objective)
        task.reason, task.evidence = rationale["reason"], rationale["evidence"]
        self.tasks.append(task)
        self.store.save(self.tasks)
        self.guard.audit.write("task_started", objective=objective, **rationale)
        try:
            self.guard.emergency_stop.check()
            workspace_items = self.tools.run("inspect_workspace", 50, reason=rationale["reason"], action="Inspect workspace", evidence="Workspace inventory", risk=Risk.LOW)
            status = self.tools.run("git_status", reason=rationale["reason"], action="Read git status", evidence="Git status output", risk=Risk.LOW)
            checkpoint = self.create_checkpoint("task_start")
            task.result = json.dumps({"plan": self.plan(objective), "workspace_items": workspace_items, "git_status": status, "checkpoint": str(checkpoint), "tools": self.tools.names()}, indent=2)
            task.status = "completed"
            task.evidence = "Workspace inspected, git status captured, and checkpoint created. No project files modified."
            self.guard.audit.write("task_completed", objective=objective, evidence=task.evidence)
        except Exception as exc:
            task.status = "stopped" if self.guard.emergency_stop.stopped else "failed"
            task.result = str(exc)
            self.guard.audit.write("task_failed", objective=objective, error=str(exc))
        task.completed = datetime.now().isoformat(timespec="seconds")
        self.store.save(self.tasks)
        return task
