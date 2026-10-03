"""Provider-neutral AI video rendering for Rooster Video Studio.

The planner creates the creative plan; this module discovers a configured renderer,
renders each scene, and assembles the final MP4. No provider credentials are stored
in the repository.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable


class VideoRendererError(RuntimeError):
    pass


class VideoRenderer:
    """Render a scene using a configured HTTP API or local renderer command."""

    def __init__(self, *, renderer_url: str | None = None,
                 renderer_command: str | None = None):
        self.renderer_url = renderer_url or os.getenv("ROOSTER_RENDERER_URL", "").strip()
        self.renderer_command = renderer_command or os.getenv("ROOSTER_RENDER_COMMAND", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.renderer_url or self.renderer_command)

    def status(self) -> str:
        if self.renderer_url:
            return f"HTTP renderer: {self.renderer_url}"
        if self.renderer_command:
            return "Local renderer command configured"
        return "No renderer configured"

    def render_scene(self, scene: dict[str, Any], output: Path, *,
                     format: str, master_visual_lock: str = "",
                     log: Callable[[str], None] | None = None) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        request = {
            "scene": scene,
            "format": format,
            "master_visual_lock": master_visual_lock,
            "output": str(output),
        }
        if self.renderer_url:
            self._render_http(request, output)
        elif self.renderer_command:
            self._render_command(request, output)
        else:
            raise VideoRendererError(
                "No video renderer is connected. Set ROOSTER_RENDERER_URL "
                "or ROOSTER_RENDER_COMMAND."
            )
        if not output.exists() or output.stat().st_size == 0:
            raise VideoRendererError(f"Renderer did not create a video: {output}")
        if log:
            log(f"Rendered scene {scene.get('scene', '?')}: {output.name}")
        return output

    def _render_http(self, request: dict[str, Any], output: Path) -> None:
        body = json.dumps(request).encode("utf-8")
        req = urllib.request.Request(
            self.renderer_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        token = os.getenv("ROOSTER_RENDERER_TOKEN", "").strip()
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise VideoRendererError(f"Renderer API request failed: {exc}") from exc

        video_url = result.get("video_url") or result.get("videoUrl") or result.get("url")
        if not video_url:
            raise VideoRendererError("Renderer API response did not contain video_url.")
        try:
            urllib.request.urlretrieve(video_url, output)
        except Exception as exc:
            raise VideoRendererError(f"Could not download rendered scene: {exc}") from exc

    def _render_command(self, request: dict[str, Any], output: Path) -> None:
        request_path = output.with_suffix(".request.json")
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        command = self.renderer_command.format(
            request=shlex.quote(str(request_path)),
            output=shlex.quote(str(output)),
        )
        try:
            completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=1800)
        except Exception as exc:
            raise VideoRendererError(f"Renderer command failed to start: {exc}") from exc
        if completed.returncode != 0:
            raise VideoRendererError(
                f"Renderer command failed ({completed.returncode}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    @staticmethod
    def find_ffmpeg() -> str | None:
        import shutil
        return shutil.which("ffmpeg")

    def assemble(self, clips: list[Path], output: Path, *, log: Callable[[str], None] | None = None) -> Path:
        if not clips:
            raise VideoRendererError("No rendered clips were produced.")
        ffmpeg = self.find_ffmpeg()
        if not ffmpeg:
            raise VideoRendererError(
                "ffmpeg is required to assemble the scenes. Install ffmpeg and ensure it is on PATH."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        concat_file = output.with_suffix(".concat.txt")
        lines = []
        for clip in clips:
            safe_path = clip.resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{safe_path}'\\n")
        concat_file.write_text("".join(lines), encoding="utf-8")
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
               "-c", "copy", str(output)]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        except Exception as exc:
            raise VideoRendererError(f"ffmpeg failed to start: {exc}") from exc
        if completed.returncode != 0:
            raise VideoRendererError(
                f"ffmpeg assembly failed: {completed.stderr.strip()[-1500:]}"
            )
        if not output.exists() or output.stat().st_size == 0:
            raise VideoRendererError("ffmpeg reported success but no MP4 was created.")
        if log:
            log(f"FINAL VIDEO: {output}")
        return output
