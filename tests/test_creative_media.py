import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from rooster_engine.creative_media import CreativeStudio, CreativeStudioError


class TestCreativeStudio(unittest.TestCase):
    def test_requires_media_renderer_for_graphics(self):
        studio = CreativeStudio(
            video_studio=object(),
            video_renderer=object(),
            openai_client=None,
        )
        with self.assertRaises(CreativeStudioError):
            studio.render_graphic(
                {"prompt": "test"},
                Path(tempfile.gettempdir()) / "x.png",
            )

    def test_plan_adds_graphics_and_commentary(self):
        class FakeStudio:
            def plan(self, idea, *, total_seconds, format):
                return {
                    "title": "Test",
                    "format": format,
                    "total_seconds": total_seconds,
                    "scenes": [{
                        "scene": 1,
                        "duration_seconds": total_seconds,
                        "prompt": "test",
                        "transition": "cut",
                        "on_screen_text": "",
                        "sound_design": "",
                    }],
                    "voiceover": "Hello",
                }

        studio = CreativeStudio(
            video_studio=FakeStudio(),
            video_renderer=object(),
            openai_client=None,
        )
        plan = studio.plan("test", total_seconds=5)
        self.assertEqual(plan["commentary"]["script"], "Hello")
        self.assertEqual(len(plan["graphics"]), 2)

    def test_openai_image_renderer_writes_base64_image(self):
        client = Mock()
        image = Mock()
        image.b64_json = base64.b64encode(b"hello").decode("ascii")
        response = Mock()
        response.data = [image]
        client.images.generate.return_value = response

        studio = CreativeStudio(
            video_studio=object(),
            video_renderer=object(),
            openai_client=client,
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "scene.png"
            result = studio._render_openai_image("race car", output)
            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes(), b"hello")
        client.images.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
