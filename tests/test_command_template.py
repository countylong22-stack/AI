import unittest

from rooster_engine.command_template import build_command


class CommandTemplateTests(unittest.TestCase):
    def test_paths_with_spaces_remain_single_arguments(self):
        command = build_command(
            "python renderer.py {request} {output}",
            request="/tmp/request file.json",
            output="/tmp/final video.mp4",
        )
        self.assertEqual(
            command,
            ["python", "renderer.py", "/tmp/request file.json", "/tmp/final video.mp4"],
        )

    def test_shell_operators_are_passed_as_arguments_not_interpreted(self):
        command = build_command(
            "renderer --request {request} {output} ; touch marker",
            request="request.json",
            output="output.mp4",
        )
        self.assertEqual(command[-3:], [";", "touch", "marker"])

    def test_unbalanced_quotes_are_rejected(self):
        with self.assertRaises(ValueError):
            build_command(
                'renderer "unterminated {request} {output}',
                request="request.json",
                output="output.mp4",
            )

    def test_unknown_placeholders_are_rejected(self):
        with self.assertRaises(ValueError):
            build_command(
                "renderer {unknown} {output}",
                request="request.json",
                output="output.mp4",
            )


if __name__ == "__main__":
    unittest.main()
