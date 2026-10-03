import unittest

from rooster_engine.video_studio import VideoStudio, VideoStudioError


class TestVideoStudioValidation(unittest.TestCase):
    def test_valid_plan(self):
        plan = {
            "format": "vertical",
            "scenes": [
                {
                    "scene": 1,
                    "duration_seconds": 5,
                    "prompt": "test",
                    "transition": "cut",
                    "on_screen_text": "",
                    "sound_design": "engine",
                },
                {
                    "scene": 2,
                    "duration_seconds": 5,
                    "prompt": "test",
                    "transition": "cut",
                    "on_screen_text": "",
                    "sound_design": "engine",
                },
            ],
        }
        VideoStudio._validate(plan, 10, "vertical")

    def test_rejects_wrong_duration(self):
        plan = {
            "format": "vertical",
            "scenes": [
                {
                    "scene": 1,
                    "duration_seconds": 5,
                    "prompt": "test",
                    "transition": "cut",
                    "on_screen_text": "",
                    "sound_design": "engine",
                }
            ],
        }
        with self.assertRaises(VideoStudioError):
            VideoStudio._validate(plan, 10, "vertical")


if __name__ == "__main__":
    unittest.main()
