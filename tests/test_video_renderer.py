import tempfile
import unittest
from pathlib import Path

from rooster_engine.video_renderer import VideoRenderer, VideoRendererError


class TestVideoRenderer(unittest.TestCase):
    def test_requires_renderer(self):
        renderer = VideoRenderer(renderer_url="", renderer_command="")
        self.assertFalse(renderer.configured)
        with self.assertRaises(VideoRendererError):
            renderer.render_scene(
                {"scene": 1, "duration_seconds": 4, "prompt": "test"},
                Path(tempfile.gettempdir()) / "missing-rooster.mp4",
                format="vertical",
            )

    def test_renderer_status(self):
        renderer = VideoRenderer(renderer_command="python renderer.py {request} {output}")
        self.assertTrue(renderer.configured)
        self.assertIn("Local renderer", renderer.status())


if __name__ == "__main__":
    unittest.main()
