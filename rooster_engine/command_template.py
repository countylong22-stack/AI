"""Safe parsing for operator-configured command templates.

Configured renderer commands are tokenized once and executed without a shell.
Only the {request} and {output} placeholders are expanded.
"""
from __future__ import annotations

import os
import shlex


def build_command(template: str, *, request: str, output: str) -> list[str]:
    if not isinstance(template, str) or not template.strip():
        raise ValueError("Renderer command cannot be empty.")

    try:
        parts = shlex.split(template, posix=(os.name != "nt"))
    except ValueError as exc:
        raise ValueError(f"Invalid renderer command quoting: {exc}") from exc

    # shlex's Windows mode preserves quote delimiters; remove only a balanced
    # pair that was used to group a single executable/argument containing spaces.
    if os.name == "nt":
        parts = [
            part[1:-1]
            if len(part) >= 2 and part[0] == part[-1] and part[0] in {"'", '"'}
            else part
            for part in parts
        ]

    values = {"request": request, "output": output}
    try:
        command = [part.format_map(values) for part in parts]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid renderer command placeholder: {exc}") from exc

    if not command or not command[0].strip():
        raise ValueError("Renderer command must start with an executable.")
    return command
