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
            action = Action(
                "git_push",
                "publish approved changes",
                "push",
                "remote accepts commit",
                Risk.CRITICAL,
            )
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
            action = Action(
                "git_commit",
                "save approved changes",
                "commit",
                "git accepts commit",
                Risk.HIGH,
            )
            guard.approve(guard.action_id(action), ttl=timedelta(seconds=-1))
            with self.assertRaises(PermissionError):
                guard.authorize(action)

    def test_approval_context_must_match_and_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            action = Action(
                "git_push",
                "publish approved changes",
                "push",
                "remote accepts commit",
                Risk.CRITICAL,
            )
            action_id = guard.action_id(action)
            guard.approve(action_id, actor="joe", task_id="task-123")

            with self.assertRaises(PermissionError):
                guard.authorize(action, actor="joe", task_id="task-999")

            with self.assertRaises(PermissionError):
                guard.authorize(action, actor="other", task_id="task-123")

            self.assertEqual(
                guard.authorize(action, actor="joe", task_id="task-123"),
                action_id,
            )
            audit = Path(tmp) / "audit.jsonl"
            audit_text = audit.read_text(encoding="utf-8")
            self.assertIn("approval_context_mismatch", audit_text)
            self.assertIn("task-123", audit_text)
            self.assertIn("joe", audit_text)

    def test_approval_rejects_empty_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(ValueError):
                guard.approve("abc", actor="")

    def test_sandbox_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            with self.assertRaises(PermissionError):
                guard.sandbox_path("../../outside.txt")

    def test_sandbox_returns_only_in_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            path = guard.sandbox_path("rooster_engine/guard.py")
            sandbox = (Path(tmp) / ".rooster" / "sandbox").resolve()
            self.assertIn(sandbox, path.parents)
            self.assertNotEqual(path, (Path(tmp) / "rooster_engine" / "guard.py").resolve())

    def test_sandbox_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = RoosterGuard(root, root / "audit.jsonl")
            outside = root / "outside"
            outside.mkdir()
            link = root / ".rooster" / "sandbox" / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable on this Windows configuration.")
            with self.assertRaises(PermissionError):
                guard.sandbox_path("escape/file.txt")

    def test_emergency_stop_blocks_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = RoosterGuard(Path(tmp), Path(tmp) / "audit.jsonl")
            guard.emergency_stop.stop()
            with self.assertRaises(RuntimeError):
                guard.authorize(
                    Action("inspect_workspace", "inspect", "list", "list returned", Risk.LOW)
                )

    def test_audit_log_is_hash_chained(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            guard = RoosterGuard(Path(tmp), audit)
            guard.authorize(Action("inspect_workspace", "inspect", "list", "inventory", Risk.LOW))
            records = [
                json.loads(line)
                for line in audit.read_text(encoding="utf-8").splitlines()
            ]
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


    def test_task_run_records_verification_and_runtime_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            engineer = AutonomousEngineer(tmp, Path(tmp) / "tasks.json")
            task = engineer.run("inspect workspace")
            self.assertEqual(task.status, "completed")
            payload = json.loads(task.result)
            self.assertIn("verification", payload)
            self.assertIn("runtime", payload)
            self.assertGreaterEqual(payload["runtime"]["steps"], 3)

    def test_task_run_stops_when_step_budget_is_too_small(self):
        from rooster_engine.runtime import RuntimeLimits

        with tempfile.TemporaryDirectory() as tmp:
            engineer = AutonomousEngineer(tmp, Path(tmp) / "tasks.json")
            task = engineer.run("inspect workspace", RuntimeLimits(max_steps=2))
            self.assertEqual(task.status, "failed")
            self.assertIn("step limit", task.result.lower())


if __name__ == "__main__":
    unittest.main()
