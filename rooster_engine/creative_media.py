"""Rooster Creative Studio: guarded video, graphics, and commentary orchestration.

Creative planning is provider-neutral. Rendering is delegated to a configured local
renderer or HTTP media service; credentials stay in environment variables.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from .video_renderer import VideoRenderer, VideoRendererError
from .video_studio import VideoStudio, VideoStudioError


class CreativeStudioError(RuntimeError):
    pass


class CreativeStudio:
    """Build complete media projects from one creative objective."""

    def __init__(self, *, video_studio: VideoStudio | None = None,
                 video_renderer: VideoRenderer | None = None):
        self.video_studio = video_studio or VideoStudio()
        self.video_renderer = video_renderer or VideoRenderer()
        self.media_url = os.getenv("ROOSTER_MEDIA_RENDERER_URL", "").strip()
        self.media_token = os.getenv("ROOSTER_MEDIA_RENDERER_TOKEN", "").strip()
        self.media_command = os.getenv("ROOSTER_MEDIA_RENDER_COMMAND", "").strip()

    def plan(self, idea: str, *, total_seconds: int = 120,
             format: str = "vertical") -> dict[str, Any]:
        plan = self.video_studio.plan(
            idea, total_seconds=total_seconds, format=format
        )
        plan.setdefault("graphics", [
            {
                "type": "thumbnail",
                "prompt": (
                    f"Create a high-impact thumbnail for: {plan.get('title', idea)}. "
                    "Keep the main subject readable at phone size and leave safe space for title text."
                ),
                "aspect_ratio": "16:9",
            },
            {
                "type": "title_card",
                "prompt": (
                    f"Create a clean title card for: {plan.get('title', idea)}. "
                    "Use the project's visual identity and no unlicensed logos."
                ),
                "aspect_ratio": "16:9",
            },
        ])
        plan.setdefault("commentary", {
            "script": plan.get("voiceover", ""),
            "voice": os.getenv("ROOSTER_COMMENTARY_VOICE", "default"),
            "pace": "energetic",
        })
        return plan

    def render_graphic(self, graphic: dict[str, Any], output: Path) -> Path:
        return self._render_media("graphic", graphic, output)

    def render_commentary(self, commentary: dict[str, Any], output: Path) -> Path:
        return self._render_media("commentary", commentary, output)

    def render_video_scene(self, scene: dict[str, Any], output: Path,
                           *, format: str, master_visual_lock: str = "") -> Path:
        return self.video_renderer.render_scene(
            scene, output, format=format, master_visual_lock=master_visual_lock
        )

    def assemble_video(self, clips: list[Path], output: Path) -> Path:
        return self.video_renderer.assemble(clips, output)

    def create_project(self, idea: str, output_dir: str | Path,
                       *, total_seconds: int = 120,
                       format: str = "vertical") -> Path:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        plan = self.plan(idea, total_seconds=total_seconds, format=format)
        plan_path = root / "project.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

        graphics = plan.get("graphics", [])
        for index, graphic in enumerate(graphics, 1):
            self.render_graphic(graphic, root / f"graphic_{index:02d}.png")

        commentary = plan.get("commentary", {})
        if commentary.get("script"):
            self.render_commentary(commentary, root / "commentary.wav")

        clips: list[Path] = []
        for scene in plan["scenes"]:
            target = root / f"scene_{int(scene['scene']):02d}.mp4"
            self.render_video_scene(
                scene,
                target,
                format=plan["format"],
                master_visual_lock=plan.get("master_visual_lock", ""),
            )
            clips.append(target)

        self.assemble_video(clips, root / "final.mp4")
        return root / "final.mp4"

    def _render_media(self, media_type: str, payload: dict[str, Any],
                      output: Path) -> Path:
        if not (self.media_url or self.media_command):
            raise CreativeStudioError(
                "No graphics/commentary renderer is connected. Set "
                "ROOSTER_MEDIA_RENDERER_URL or ROOSTER_MEDIA_RENDER_COMMAND."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        request = {
            "type": media_type,
            "payload": payload,
            "output": str(output),
        }
        if self.media_url:
            body = json.dumps(request).encode("utf-8")
            req = urllib.request.Request(
                self.media_url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            if self.media_token:
                req.add_header("Authorization", f"Bearer {self.media_token}")
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    result = json.loads(response.read().decode("utf-8"))
                url = result.get("url") or result.get("media_url")
                if url:
                    urllib.request.urlretrieve(url, output)
                elif not output.exists():
                    raise CreativeStudioError("Media renderer returned no output URL.")
            except Exception as exc:
                if isinstance(exc, CreativeStudioError):
                    raise
                raise CreativeStudioError(f"Media renderer request failed: {exc}") from exc
        else:
            request_path = output.with_suffix(output.suffix + ".request.json")
            request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
            command = self.media_command.format(
                request=str(request_path),
                output=str(output),
            )
            try:
                completed = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=1800
                )
            except Exception as exc:
                raise CreativeStudioError(f"Media command failed to start: {exc}") from exc
            if completed.returncode != 0:
                raise CreativeStudioError(
                    f"Media command failed ({completed.returncode}): "
                    f"{completed.stderr.strip() or completed.stdout.strip()}"
                )
        if not output.exists() or output.stat().st_size == 0:
            raise CreativeStudioError(f"Media renderer did not create {output}.")
        return output
