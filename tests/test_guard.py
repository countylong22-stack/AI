import tempfile
import unittest
from pathlib import Path

from rooster_engine.guard import Action, Risk, RoosterGuard
from rooster_engine.core import AutonomousEngineer


class GuardTests(unittest.TestCase):
    def test_unknown_tool_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.authorize(Action("unknown", "test", "test", "test", Risk.LOW))

    def test_high_risk_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            action = Action("git_push", "publish approved changes", "push", "remote accepts commit", Risk.CRITICAL)
            with self.assertRaises(PermissionError):
                guard.authorize(action)
            action_id = guard.action_id(action)
            guard.approve(action_id)
            self.assertEqual(guard.authorize(action), action_id)

    def test_sandbox_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.sandbox_path("../../outside.txt")

    def test_emergency_stop_blocks_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            guard.emergency_stop.stop()
            with self.assertRaises(RuntimeError):
                guard.authorize(Action("inspect_workspace", "inspect", "list", "list returned", Risk.LOW))

    def test_reason_action_evidence_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            engineer = AutonomousEngineer(tmp, Path(tmp) / "tasks.json")
            task = engineer.run("inspect this test workspace")
            self.assertEqual(task.status, "completed")
            self.assertTrue(task.reason)
            self.assertTrue(task.evidence)
            audit = Path(tmp) / ".rooster" / "audit.jsonl"
            self.assertTrue(audit.exists())
            text = audit.read_text(encoding="utf-8")
            self.assertIn("task_started", text)
            self.assertIn("task_completed", text)


if __name__ == "__main__":
    unittest.main()
