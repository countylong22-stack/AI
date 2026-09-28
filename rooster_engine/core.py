from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Any
import json
import subprocess
from datetime import datetime


@dataclass
class Task:
    objective: str
    status: str = "queued"
    created: str = ""
    completed: str = ""
    result: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat(timespec="seconds")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, function: Callable[..., Any]) -> None:
        self._tools[name] = function

    def names(self) -> list[str]:
        return sorted(self._tools)

    def run(self, name: str, *args, **kwargs) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](*args, **kwargs)


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()

    def inspect(self, limit: int = 100) -> list[dict[str, Any]]:
        items = []
        for path in sorted(self.root.iterdir(), key=lambda p: p.name.lower()):
            items.append({
                "name": path.name,
                "type": "directory" if path.is_dir() else "file",
                "path": str(path),
            })
            if len(items) >= limit:
                break
        return items

    def read_text(self, relative_path: str, max_chars: int = 50000) -> str:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Path escapes workspace.")
        return path.read_text(encoding="utf-8")[:max_chars]

    def git_status(self) -> str:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return (result.stdout + result.stderr).strip()


class TaskStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [Task(**item) for item in data]
        except (OSError, ValueError, TypeError):
            return []

    def save(self, tasks: list[Task]) -> None:
        self.path.write_text(
            json.dumps([asdict(task) for task in tasks], indent=2),
            encoding="utf-8",
        )


class AutonomousEngineer:
    def __init__(self, workspace: str | Path, memory_file: str | Path):
        self.workspace = Workspace(workspace)
        self.store = TaskStore(memory_file)
        self.tasks = self.store.load()
        self.tools = ToolRegistry()
        self._register_tools()

    def _register_tools(self) -> None:
        self.tools.register("inspect_workspace", self.workspace.inspect)
        self.tools.register("git_status", self.workspace.git_status)
        self.tools.register("read_file", self.workspace.read_text)

    def plan(self, objective: str) -> list[str]:
        return [
            "Inspect the project workspace",
            "Identify relevant files and project type",
            "Select safe engineering tools",
            "Execute non-destructive inspection",
            "Verify results and report",
        ]

    def run(self, objective: str) -> Task:
        task = Task(objective=objective, status="running")
        self.tasks.append(task)
        self.store.save(self.tasks)

        try:
            workspace_items = self.tools.run("inspect_workspace", 50)
            status = self.tools.run("git_status")

            task.result = json.dumps(
                {
                    "plan": self.plan(objective),
                    "workspace_items": workspace_items,
                    "git_status": status,
                    "tools": self.tools.names(),
                },
                indent=2,
            )
            task.status = "completed"
        except Exception as exc:
            task.status = "failed"
            task.result = str(exc)

        task.completed = datetime.now().isoformat(timespec="seconds")
        self.store.save(self.tasks)
        return task
