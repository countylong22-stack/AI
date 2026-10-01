import tempfile
import unittest
from pathlib import Path

from rooster_engine.core import AutonomousEngineer
from rooster_engine.guard import Action, Risk
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

    def test_guarded_test_suite_records_command_exit_and_bounded_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sample.py").write_text(
                "import unittest\n\nclass Sample(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            engineer = AutonomousEngineer(root, root / ".rooster" / "tasks.json")
            action = Action(
                "run_tests",
                "test verification",
                "Run fixed unittest discovery suite",
                "test suite evidence",
                Risk.MEDIUM,
                "tests",
            )
            engineer.guard.approve(engineer.guard.action_id(action))
            result = engineer.tools.run(
                "run_tests",
                reason="test verification",
                action="Run fixed unittest discovery suite",
                evidence="test suite evidence",
                risk=Risk.MEDIUM,
                target="tests",
            )
            self.assertTrue(result.success)
            self.assertEqual(result.evidence["returncode"], 0)
            self.assertEqual(result.evidence["command"][1:5],
                             ["-m", "unittest", "discover", "-s"])
            self.assertFalse(result.evidence["timed_out"])
            self.assertLessEqual(
                result.evidence["stdout_chars"], result.evidence["max_output_chars"]
            )
            audit = root / ".rooster" / "audit.jsonl"
            audit_text = audit.read_text(encoding="utf-8")
            self.assertIn("test_suite_started", audit_text)
            self.assertIn("test_suite_completed", audit_text)


if __name__ == "__main__":
    unittest.main()
