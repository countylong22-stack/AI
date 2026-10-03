"""Rooster Creative Studio: guarded video, graphics, and commentary orchestration.

The studio is provider-neutral at the boundary. It can use an explicitly configured
media service, or (when enabled) OpenAI image generation plus local ffmpeg to produce
a real MP4 without routing the job through a third-party creator platform.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from openai import OpenAI

from .video_renderer import VideoRenderer, VideoRendererError
from .video_studio import VideoStudio, VideoStudioError


class CreativeStudioError(RuntimeError):
    pass


class CreativeStudio:
    """Build complete media projects from one creative objective."""

    def __init__(
        self,
        *,
        video_studio: VideoStudio | None = None,
        video_renderer: VideoRenderer | None = None,
        openai_client: OpenAI | None = None,
    ):
        self.video_studio = video_studio or VideoStudio()
        self.video_renderer = video_renderer or VideoRenderer()
        self.media_url = os.getenv("ROOSTER_MEDIA_RENDERER_URL", "").strip()
        self.media_token = os.getenv("ROOSTER_MEDIA_RENDERER_TOKEN", "").strip()
        self.media_command = os.getenv("ROOSTER_MEDIA_RENDER_COMMAND", "").strip()
        self.openai_media = os.getenv("ROOSTER_OPENAI_MEDIA", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.openai_client = openai_client if openai_client is not None else (
            OpenAI() if self.openai_media else None
        )
        self.image_model = os.getenv("ROOSTER_IMAGE_MODEL", "gpt-image-2")

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
        if self.media_url or self.media_command:
            return self._render_media("graphic", graphic, output)
        if self.openai_client is None:
            raise CreativeStudioError(
                "No graphics renderer is connected. Set ROOSTER_OPENAI_MEDIA=true "
                "or configure ROOSTER_MEDIA_RENDERER_URL/ROOSTER_MEDIA_RENDER_COMMAND."
            )
        return self._render_openai_image(graphic.get("prompt", ""), output)

    def render_commentary(self, commentary: dict[str, Any], output: Path) -> Path:
        return self._render_media("commentary", commentary, output)

    def render_video_scene(
        self,
        scene: dict[str, Any],
        output: Path,
        *,
        format: str,
        master_visual_lock: str = "",
    ) -> Path:
        if self.video_renderer.configured:
            return self.video_renderer.render_scene(
                scene, output, format=format, master_visual_lock=master_visual_lock
            )

        if self.openai_client is None:
            raise VideoRendererError(
                "No video renderer is connected. Set ROOSTER_RENDERER_URL or "
                "ROOSTER_RENDER_COMMAND, or enable ROOSTER_OPENAI_MEDIA=true for "
                "OpenAI-generated scene visuals assembled into an MP4."
            )

        prompt = (
            f"{master_visual_lock}\n\n"
            f"SCENE {scene.get('scene', '')}: {scene.get('prompt', '')}\n"
            f"Sound design is handled separately: {scene.get('sound_design', '')}"
        ).strip()
        image_path = output.with_suffix(".scene.png")
        self._render_openai_image(prompt, image_path)
        return self._image_to_video(
            image_path,
            output,
            int(scene.get("duration_seconds", 1)),
            format=format,
        )

    def assemble_video(self, clips: list[Path], output: Path) -> Path:
        return self.video_renderer.assemble(clips, output)

    def create_project(
        self,
        idea: str,
        output_dir: str | Path,
        *,
        total_seconds: int = 120,
        format: str = "vertical",
    ) -> Path:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        plan = self.plan(idea, total_seconds=total_seconds, format=format)
        plan_path = root / "project.json"
        plan_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        graphics = plan.get("graphics", [])
        for index, graphic in enumerate(graphics, 1):
            self.render_graphic(graphic, root / f"graphic_{index:02d}.png")

        commentary = plan.get("commentary", {})
        if commentary.get("script") and (self.media_url or self.media_command):
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

    def _render_openai_image(self, prompt: str, output: Path) -> Path:
        if not prompt.strip():
            raise CreativeStudioError("Image prompt cannot be empty.")
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = self.openai_client.images.generate(
                model=self.image_model,
                prompt=prompt,
                size=self._image_size(output),
            )
            item = response.data[0]
            encoded = getattr(item, "b64_json", None)
            if encoded:
                output.write_bytes(base64.b64decode(encoded))
            else:
                url = getattr(item, "url", None)
                if not url:
                    raise CreativeStudioError(
                        "OpenAI image generation returned neither b64_json nor url."
                    )
                urllib.request.urlretrieve(url, output)
        except Exception as exc:
            if isinstance(exc, CreativeStudioError):
                raise
            raise CreativeStudioError(f"OpenAI image generation failed: {exc}") from exc

        if not output.exists() or output.stat().st_size == 0:
            raise CreativeStudioError(f"OpenAI did not create {output}.")
        return output

    @staticmethod
    def _image_size(output: Path) -> str:
        # Graphics are intentionally landscape; scene images follow the final video
        # format in _image_to_video and are generated at a practical API size.
        return "1536x1024" if output.suffix.lower() == ".png" else "1536x1024"

    @staticmethod
    def _image_to_video(
        image: Path,
        output: Path,
        duration_seconds: int,
        *,
        format: str,
    ) -> Path:
        import shutil

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise VideoRendererError(
                "ffmpeg is required for Rooster's OpenAI media fallback."
            )
        if duration_seconds < 1:
            raise VideoRendererError("Scene duration must be at least one second.")

        dimensions = {
            "vertical": (1080, 1920),
            "landscape": (1920, 1080),
            "square": (1080, 1080),
        }
        width, height = dimensions.get(format, dimensions["vertical"])
        output.parent.mkdir(parents=True, exist_ok=True)

        # A restrained Ken Burns move turns each generated still into motion while
        # preserving the exact car identity across a scene.
        frames = duration_seconds * 30
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0005,1.12)':d={frames}:s={width}x{height}:fps=30,"
            "format=yuv420p"
        )
        cmd = [
            ffmpeg, "-y", "-loop", "1", "-i", str(image),
            "-vf", vf, "-t", str(duration_seconds), "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ]
        try:
            completed = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800
            )
        except Exception as exc:
            raise VideoRendererError(f"ffmpeg failed to start: {exc}") from exc
        if completed.returncode != 0:
            raise VideoRendererError(
                f"ffmpeg scene generation failed: {completed.stderr.strip()[-1500:]}"
            )
        if not output.exists() or output.stat().st_size == 0:
            raise VideoRendererError("ffmpeg reported success but no scene MP4 was created.")
        return output

    def _render_media(
        self, media_type: str, payload: dict[str, Any], output: Path
    ) -> Path:
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
                self.media_url,
                data=body,
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
            request_path.write_text(
                json.dumps(request, indent=2), encoding="utf-8"
            )
            command = self.media_command.format(
                request=str(request_path),
                output=str(output),
            )
            try:
                completed = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=1800
                )
            except Exception as exc:
                raise CreativeStudioError(
                    f"Media command failed to start: {exc}"
                ) from exc
            if completed.returncode != 0:
                raise CreativeStudioError(
                    f"Media command failed ({completed.returncode}): "
                    f"{completed.stderr.strip() or completed.stdout.strip()}"
                )
        if not output.exists() or output.stat().st_size == 0:
            raise CreativeStudioError(f"Media renderer did not create {output}.")
        return output
