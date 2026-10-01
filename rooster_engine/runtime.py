from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class RuntimeLimits:
    max_steps: int = 10
    max_failures: int = 3
    max_duration_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if self.max_failures < 0:
            raise ValueError("max_failures must be non-negative")
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")


class RuntimeBudget:
    """Bounded execution budget checked before every autonomous step."""

    def __init__(self, limits: RuntimeLimits | None = None) -> None:
        self.limits = limits or RuntimeLimits()
        self.started = monotonic()
        self.steps = 0
        self.failures = 0

    def check(self) -> None:
        if self.steps >= self.limits.max_steps:
            raise RuntimeError("Rooster runtime step limit reached.")
        if self.failures >= self.limits.max_failures:
            raise RuntimeError("Rooster runtime failure limit reached.")
        if monotonic() - self.started >= self.limits.max_duration_seconds:
            raise RuntimeError("Rooster runtime duration limit reached.")

    def begin_step(self) -> None:
        self.check()
        self.steps += 1

    def record_failure(self) -> None:
        self.failures += 1
