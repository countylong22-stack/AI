from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    area: str
    priority: str
    file: str
    evidence: str
    recommendation: str


class CodebaseAnalyzer:
    """Deterministic, read-only source inspection for evidence-backed engineering plans."""

    DEFAULT_EXTENSIONS = {".py", ".ps1", ".yml", ".yaml", ".md", ".toml", ".json"}

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def analyze(
        self,
        inventory: list[dict[str, Any]],
        *,
        max_files: int = 40,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        discovered = []
        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            if ".rooster" in path.parts or "__pycache__" in path.parts or ".git" in path.parts:
                continue
            if path.suffix.lower() in self.DEFAULT_EXTENSIONS:
                discovered.append(path)
        files = sorted(discovered, key=lambda path: str(path).lower())[:max_files]
        sources: dict[str, str] = {}
        for path in files:
            try:
                relative = path.relative_to(self.workspace)
                sources[relative.as_posix()] = path.read_text(encoding="utf-8")[:max_chars]
            except (OSError, UnicodeError, ValueError):
                continue

        findings = self._findings(sources)
        return {
            "files_read": sorted(sources),
            "file_count": len(sources),
            "findings": [finding.__dict__ for finding in findings],
            "read_only": True,
        }

    def _findings(self, sources: dict[str, str]) -> list[Finding]:
        joined = "\n".join(
            f"--- {name} ---\n{text}" for name, text in sources.items()
        )
        findings: list[Finding] = []

        if (
            "write_sandbox" in joined
            and ".rooster/sandbox" in joined
            and "PROTECTED_PATHS" not in joined
        ):
            findings.append(Finding(
                "self-modification",
                "HIGH",
                self._preferred_file(
                    sources,
                    "rooster_engine/core.py",
                    ("write_sandbox", ".rooster/sandbox"),
                ),
                "Workspace writes are routed to .rooster/sandbox, but no protected-path policy for core security modules is visible.",
                "Add an explicit protected-path policy for guard, approval, emergency-stop, policy, and CI security files.",
            ))

        command_source = sources.get("rooster_engine/command.py", "")
        if command_source and (
            "DEFAULT_ALLOWED" not in command_source
            or "shell=False" not in command_source
            or "_validate_arguments" not in command_source
            or "allow_general_python: bool = False" not in command_source
        ):
            findings.append(Finding(
                "command execution",
                "MEDIUM",
                "rooster_engine/command.py",
                "Command execution is missing one or more explicit controls: executable allowlisting, shell=False, argument-level validation, or a default-deny general Python mode.",
                "Keep executable and argument policies explicit, require approval, and preserve bounded runtime/output.",
            ))

        guard_source = sources.get("rooster_engine/guard.py", "")
        if "git_push" in guard_source and "Permission.NETWORK" not in guard_source:
            findings.append(Finding(
                "network access",
                "HIGH",
                "rooster_engine/guard.py",
                "A network-capable git_push policy exists without an explicit network permission classification.",
                "Keep network access explicitly classified, approval-gated, and host-allowlisted before enabling it.",
            ))

        runtime_source = sources.get("rooster_engine/runtime.py", "")
        command_source = sources.get("rooster_engine/command.py", "")
        missing_runtime_controls = [
            name for name in ("max_output_chars", "max_write_bytes")
            if name not in runtime_source
        ]
        if "timeout_seconds" not in command_source:
            missing_runtime_controls.append("subprocess timeout")
        if missing_runtime_controls:
            findings.append(Finding(
                "runtime limits",
                "MEDIUM",
                "rooster_engine/runtime.py",
                "Runtime resource controls are missing: " + ", ".join(missing_runtime_controls) + ".",
                "Add bounded resource budgets for each missing control and expose evidence when a budget is consumed.",
            ))

        verification = sources.get("rooster_engine/verification.py", "")
        if "verify_task_observation" in verification and "subprocess" not in verification:
            findings.append(Finding(
                "verification",
                "HIGH",
                "rooster_engine/verification.py",
                "Verification validates observations and checkpoint existence but does not independently execute the project's test suite.",
                "Add guarded test execution that records the exact command, exit status, and bounded output as evidence.",
            ))

        if "shutil.copytree" in joined and "restore" not in joined.lower():
            findings.append(Finding(
                "checkpoint recovery",
                "MEDIUM",
                self._preferred_file(
                    sources,
                    "rooster_engine/core.py",
                    ("shutil.copytree", "checkpoint"),
                ),
                "Checkpoints are created as snapshots, but no restore operation or manifest/hash verification is visible.",
                "Add an operator-controlled restore path plus manifest/hash verification.",
            ))

        if "record_hash" in joined and "verify_chain" not in joined:
            findings.append(Finding(
                "audit integrity",
                "MEDIUM",
                self._preferred_file(
                    sources,
                    "rooster_engine/guard.py",
                    ("record_hash", "hash chain"),
                ),
                "Audit records form a hash chain, but no chain verification routine is exposed.",
                "Add an audit-chain verification function that detects truncation, reordering, or tampering.",
            ))

        if not findings:
            findings.append(Finding(
                "inspection",
                "INFO",
                "",
                "No configured heuristic matched the inspected source.",
                "Review the raw inventory and add domain-specific analyzers as the engine grows.",
            ))
        return findings

    @staticmethod
    def _preferred_file(
        sources: dict[str, str],
        preferred: str,
        markers: tuple[str, ...],
    ) -> str:
        preferred_text = sources.get(preferred, "")
        if preferred_text and any(marker in preferred_text for marker in markers):
            return preferred
        return CodebaseAnalyzer._first_matching_file(sources, markers)

    @staticmethod
    def _first_matching_file(sources: dict[str, str], markers: tuple[str, ...]) -> str:
        for path, text in sources.items():
            if path == "rooster_engine/analysis.py":
                continue
            if any(marker in text for marker in markers):
                return path
        return "not specified"


def prioritize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    return sorted(
        findings,
        key=lambda item: (order.get(item.get("priority", "INFO"), 9), item.get("area", "")),
    )
