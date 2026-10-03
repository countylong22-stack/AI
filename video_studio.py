"""CLI for Rooster Autonomous Engineer's OpenAI Video Studio."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rooster_engine.video_studio import VideoStudio, VideoStudioError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create AI-video-ready scene plans with OpenAI."
    )
    parser.add_argument("idea", help="The video idea to turn into a production plan.")
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument(
        "--format",
        choices=("vertical", "landscape", "square"),
        default="vertical",
    )
    parser.add_argument("--output", default="video_projects/rooster_video_plan.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set. Set it as an environment variable or GitHub Secret.",
            file=sys.stderr,
        )
        return 2

    try:
        studio = VideoStudio()
        plan = studio.plan(
            args.idea,
            total_seconds=args.seconds,
            format=args.format,
        )
        path = studio.save(plan, args.output)
    except VideoStudioError as exc:
        print(f"Video Studio error: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {path}")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
