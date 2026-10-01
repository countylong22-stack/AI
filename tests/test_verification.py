import tempfile
import unittest
from pathlib import Path

from rooster_engine.verification import VerificationEngine


class VerificationTests(unittest.TestCase):
    def test_checkpoint_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint"
            path.mkdir()
            result = VerificationEngine().verify_checkpoint(path)
            self.assertTrue(result.success)
            self.assertTrue(result.evidence["exists"])

    def test_missing_checkpoint_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = VerificationEngine().verify_checkpoint(Path(tmp) / "missing")
            self.assertFalse(result.success)

    def test_task_observation_verification(self):
        result = VerificationEngine().verify_task_observation(
            [{"name": "README.md"}], " M README.md"
        )
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
