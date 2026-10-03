"""OpenAI-powered video pre-production for Rooster Autonomous Engineer.

This module turns a natural-language video idea into a structured scene plan,
consistent visual prompts, voiceover, and editing metadata. It intentionally
does not store API keys in source code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_MODEL = os.getenv("ROOSTER_VIDEO_MODEL", "gpt-6-luna")


class VideoStudioError(RuntimeError):
    """Raised when the video studio cannot complete a request."""


SYSTEM_PROMPT = """You are Rooster Video Studio, an expert AI video director.
Turn a user's video idea into a production-ready plan for an AI video generator.

Return ONLY valid JSON with this shape:
{
  "title": "string",
  "format": "vertical" | "landscape" | "square",
  "total_seconds": integer,
  "master_visual_lock": "string",
  "scenes": [
    {
      "scene": integer,
      "duration_seconds": integer,
      "prompt": "string",
      "transition": "string",
      "on_screen_text": "string",
      "sound_design": "string"
    }
  ],
  "voiceover": "string",
  "edit_notes": ["string"]
}

Rules:
- Preserve exact character/vehicle identity across scenes.
- For racing videos, describe physically believable racing, camera movement,
  lighting, tire behavior, braking, and track continuity.
- Never invent real sponsorships or claim a fictional event is real.
- Keep prompts suitable for mainstream AI video generators.
- Total scene duration must equal total_seconds.
- The master_visual_lock must be reusable at the start of every scene prompt.
"""


class VideoStudio:
    def __init__(self, model: str = DEFAULT_MODEL, client: OpenAI | None = None):
        self.model = model
        self.client = client or OpenAI()

    def plan(self, idea: str, *, total_seconds: int = 120,
             format: str = "vertical") -> dict[str, Any]:
        if not idea.strip():
            raise VideoStudioError("Video idea cannot be empty.")
        if total_seconds < 1 or total_seconds > 900:
            raise VideoStudioError("total_seconds must be between 1 and 900.")
        if format not in {"vertical", "landscape", "square"}:
            raise VideoStudioError("format must be vertical, landscape, or square.")

        prompt = (
            f"Create a {total_seconds}-second {format} video plan.\n"
            f"VIDEO IDEA:\n{idea.strip()}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
            )
        except Exception as exc:
            raise VideoStudioError(f"OpenAI request failed: {exc}") from exc

        raw = response.output_text.strip()
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VideoStudioError(
                "OpenAI returned non-JSON output. Try again with the same request."
            ) from exc

        self._validate(plan, total_seconds, format)
        return plan

    @staticmethod
    def _validate(plan: dict[str, Any], total_seconds: int, format: str) -> None:
        if not isinstance(plan, dict):
            raise VideoStudioError("Video plan is not an object.")
        scenes = plan.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise VideoStudioError("Video plan contains no scenes.")

        duration = sum(int(scene["duration_seconds"]) for scene in scenes)
        if duration != total_seconds:
            raise VideoStudioError(
                f"Scene durations total {duration}s; expected {total_seconds}s."
            )
        if plan.get("format") != format:
            raise VideoStudioError("Video plan format does not match the request.")

        for scene in scenes:
            for key in ("scene", "duration_seconds", "prompt", "transition",
                        "on_screen_text", "sound_design"):
                if key not in scene:
                    raise VideoStudioError(f"Scene is missing required field: {key}.")

    @staticmethod
    def save(plan: dict[str, Any], output: str | Path) -> Path:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
