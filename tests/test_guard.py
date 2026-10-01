import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from rooster_engine.guard import Action, Risk, RoosterGuard
from rooster_engine.core import AutonomousEngineer


class GuardTests(unittest.TestCase):
    def test_unknown_tool_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.authorize(Action("unknown", "test", "test", "test", Risk.LOW))

    def test_high_risk_requires_exact_one_time_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            action = Action("git_push", "publish approved changes", "push", "remote accepts commit", Risk.CRITICAL)
            with self.assertRaises(PermissionError):
                guard.authorize(action)
            action_id = guard.action_id(action)
            guard.approve(action_id)
            self.assertEqual(guard.authorize(action), action_id)
            with self.assertRaises(PermissionError):
                guard.authorize(action)

    def test_expired_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            action = Action("git_commit", "save approved changes", "commit", "git accepts commit", Risk.HIGH)
            guard.approve(guard.action_id(action), ttl=timedelta(seconds=-1))
            with self.assertRaises(PermissionError):
                guard.authorize(action)

    def test_sandbox_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.sandbox_path("../../outside.txt")

    def test_sandbox_protects_safety_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.sandbox_path("rooster_engine/guard.py")

    def test_emergency_stop_blocks_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            guard.emergency_stop.stop()
            with self.assertRaises(RuntimeError):
                guard.authorize(Action("inspect_workspace", "inspect", "list", "list returned", Risk.LOW))

    def test_audit_log_is_hash_chained(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            guard = RoosterGuard(Path(tmp), audit)
            guard.authorize(Action("inspect_workspace", "inspect", "list", "inventory", Risk.LOW))
            records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            self.assertGreaterEqual(len(records), 1)
            self.assertTrue(records[0]["record_hash"])
            self.assertEqual(records[0]["previous_hash"], "")
            if len(records) > 1:
                self.assertEqual(records[1]["previous_hash"], records[0]["record_hash"])

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
