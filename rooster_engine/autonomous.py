"""Guarded autonomous coding loop for Rooster.

Rooster can independently inspect, reason, edit non-protected project files, run the
repository test suite, and iterate. High-risk operations, protected system files,
network publishing, destructive actions, and the emergency stop remain outside
autonomous authority.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from .core import AutonomousEngineer
from .guard import Action, Risk
from .runtime import RuntimeLimits


DEFAULT_MODEL = os.getenv("ROOSTER_AGENT_MODEL", "gpt-6-luna")
MAX_ITERATIONS = 3
MAX_READ_FILES = 8
MAX_FILE_CHARS = 30000
MAX_WRITE_FILES = 6
MAX_WRITE_CHARS = 100000


@dataclass
class AutonomousRun:
    task_id: str
    objective: str
    status: str
    iterations: int
    summary: str
    evidence: list[dict[str, Any]]


class AutonomousCoder:
    """A bounded self-directed engineering loop using RoosterGuard."""

    def __init__(
        self,
        engineer: AutonomousEngineer,
        *,
        model: str = DEFAULT_MODEL,
        client: OpenAI | None = None,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        if max_iterations < 1 or max_iterations > 10:
            raise ValueError("max_iterations must be between 1 and 10.")
        self.engineer = engineer
        self.model = model
        self.client = client or OpenAI()
        self.max_iterations = max_iterations

    def run(self, objective: str, *, task_id: str = "autonomous-task") -> AutonomousRun:
        if not objective.strip():
            raise ValueError("Autonomous objective cannot be empty.")

        guard = self.engineer.guard
        guard.emergency_stop.check()
        evidence: list[dict[str, Any]] = []
        task_id = task_id or "autonomous-task"

        for iteration in range(1, self.max_iterations + 1):
            guard.emergency_stop.check()
            inventory = self.engineer.workspace.inspect(limit=100)
            context = self._planning_context(inventory)
            plan = self._json_call(
                self._planning_prompt(objective, context, iteration)
            )
            read_paths = self._safe_read_paths(plan.get("read_paths", []))

            files: dict[str, str] = {}
            for relative_path in read_paths:
                guard.emergency_stop.check()
                files[relative_path] = self.engineer.workspace.read_text(
                    relative_path, max_chars=MAX_FILE_CHARS
                )

            patch_request = self._json_call(
                self._patch_prompt(objective, iteration, context, files, plan)
            )
            patches = patch_request.get("patches", [])
            if not isinstance(patches, list):
                raise RuntimeError("Autonomous model returned invalid patches.")
            patches = patches[:MAX_WRITE_FILES]

            changed = 0
            for patch in patches:
                guard.emergency_stop.check()
                if not isinstance(patch, dict):
                    continue
                path = str(patch.get("path", "")).strip()
                content = patch.get("content")
                if not path or not isinstance(content, str):
                    continue
                if len(content) > MAX_WRITE_CHARS:
                    raise RuntimeError(f"Autonomous patch is too large: {path}")

                action = Action(
                    "write_project_file",
                    f"Autonomous engineering objective: {objective}",
                    f"Write approved autonomous change to {path}",
                    "File content produced by the configured reasoning model; tests will verify it.",
                    Risk.MEDIUM,
                    path,
                )
                action_id = guard.action_id(action)
                guard.approve(action_id, actor="autonomous", task_id=task_id)
                self.engineer.tools.run(
                    "write_project_file",
                    path,
                    content,
                    reason=action.reason,
                    action=action.action,
                    evidence=action.evidence,
                    risk=Risk.MEDIUM,
                    target=path,
                    actor="autonomous",
                    task_id=task_id,
                )
                changed += 1

            test_action = Action(
                "run_tests",
                f"Verify autonomous engineering objective: {objective}",
                "Run the repository unittest suite",
                "Fresh unittest exit status and captured output",
                Risk.MEDIUM,
                "tests",
            )
            test_id = guard.action_id(test_action)
            guard.approve(test_id, actor="autonomous", task_id=task_id)
            verification = self.engineer.tools.run(
                "run_tests",
                reason=test_action.reason,
                action=test_action.action,
                evidence=test_action.evidence,
                risk=Risk.MEDIUM,
                target="tests",
                actor="autonomous",
                task_id=task_id,
            )
            verification_evidence = getattr(verification, "evidence", {})
            success = bool(getattr(verification, "success", False))
            evidence.append(
                {
                    "iteration": iteration,
                    "files_changed": changed,
                    "tests_passed": success,
                    "test_evidence": verification_evidence,
                }
            )
            if success:
                summary = self._summary_call(objective, evidence)
                guard.audit.write(
                    "autonomous_task_completed",
                    task_id=task_id,
                    objective=objective,
                    iterations=iteration,
                    files_changed=changed,
                )
                return AutonomousRun(task_id, objective, "completed", iteration, summary, evidence)

            if changed == 0:
                break

        guard.audit.write(
            "autonomous_task_stopped",
            task_id=task_id,
            objective=objective,
            iterations=len(evidence),
            reason="bounded_iteration_limit_or_no_change",
        )
        return AutonomousRun(
            task_id,
            objective,
            "stopped",
            len(evidence),
            "Rooster stopped after its bounded autonomous loop without proving the requested outcome.",
            evidence,
        )

    @staticmethod
    def _planning_context(inventory: list[dict[str, Any]]) -> str:
        return json.dumps(inventory[:100], indent=2)

    @staticmethod
    def _safe_read_paths(paths: Any) -> list[str]:
        if not isinstance(paths, list):
            return []
        result: list[str] = []
        for value in paths[:MAX_READ_FILES]:
            if isinstance(value, str) and value.strip():
                result.append(value.strip())
        return result

    def _planning_prompt(self, objective: str, context: str, iteration: int) -> str:
        return f"""You are Rooster Autonomous Engineer.
You are operating inside a guarded local software repository.
Objective: {objective}
Iteration: {iteration}/{self.max_iterations}

Workspace inventory:
{context}

Return ONLY JSON:
{{"read_paths":["relative/path.py"],"approach":"short explanation"}}

Choose only files relevant to the objective. Never request secrets, .env files,
credentials, protected Rooster security files, .github/workflows, or files outside
the workspace. The next stage will receive the selected file contents."""

    def _patch_prompt(
        self,
        objective: str,
        iteration: int,
        context: str,
        files: dict[str, str],
        plan: dict[str, Any],
    ) -> str:
        return f"""You are Rooster Autonomous Engineer.
Implement this objective in the current repository: {objective}
Iteration: {iteration}/{self.max_iterations}
Plan:
{json.dumps(plan, indent=2)}

Workspace inventory:
{context}

Current relevant files:
{json.dumps(files, indent=2)}

Return ONLY JSON:
{{"patches":[{{"path":"relative/path.py","content":"complete new file content"}}],"intent":"what changed"}}

Rules:
- Make the smallest coherent change that advances the objective.
- Return COMPLETE file contents, not diffs.
- You may change only non-protected project files.
- Never modify rooster_engine/guard.py, core.py, command.py, runtime.py,
  verification.py, analysis.py, app.py, SECURITY.md, .github/workflows/*,
  credentials, secrets, or environment files.
- Never add API keys or tokens.
- Keep changes compatible with the existing architecture.
- Prefer tests when the objective is a code change.
- Maximum {MAX_WRITE_FILES} files and {MAX_WRITE_CHARS} characters per file."""

    def _summary_call(self, objective: str, evidence: list[dict[str, Any]]) -> str:
        prompt = (
            "Summarize the completed autonomous engineering task in 4 concise sentences. "
            "Do not claim anything beyond this evidence.\n"
            f"Objective: {objective}\nEvidence: {json.dumps(evidence, default=str)}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions="You are a precise software engineering reviewer.",
                input=prompt,
            )
            return response.output_text.strip()
        except Exception:
            return "Rooster completed the bounded task and recorded fresh test evidence."

    def _json_call(self, prompt: str) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions="Return only valid JSON. No markdown fences.",
                input=prompt,
            )
        except Exception as exc:
            raise RuntimeError(f"Autonomous model request failed: {exc}") from exc
        raw = response.output_text.strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Autonomous model returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Autonomous model returned a non-object JSON value.")
        return value
