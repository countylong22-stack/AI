import tempfile
import unittest
from pathlib import Path

from rooster_engine.command import CommandExecutor
from rooster_engine.guard import RoosterGuard
from rooster_engine.runtime import RuntimeBudget, RuntimeLimits


class CommandExecutorTests(unittest.TestCase):
    def _executor(self, tmp, **kwargs):
        root = Path(tmp)
        guard = RoosterGuard(root, root / ".rooster" / "audit.jsonl")
        return CommandExecutor(guard, **kwargs), guard

    def test_non_allowlisted_command_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(tmp, allowed_commands={"python"})
            with self.assertRaises(PermissionError):
                executor.run(["cmd.exe", "/c", "echo", "blocked"],
                             reason="test", evidence="denial")

    def test_allowlisted_command_requires_exact_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, guard = self._executor(tmp, allowed_commands={"python"})
            command = ["python", "-c", "print('ok')"]
            with self.assertRaises(PermissionError):
                executor.run(command, reason="test", evidence="stdout")
            from rooster_engine.guard import Action, Risk
            action = Action(
                "run_command", "test", "Execute allowlisted command: python -c print('ok')",
                "stdout", Risk.MEDIUM
            )
            guard.approve(guard.action_id(action))
            result = executor.run(command, reason="test", evidence="stdout")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "ok")

    def test_shell_is_not_used_and_cwd_is_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, guard = self._executor(tmp, allowed_commands={"python"})
            from rooster_engine.guard import Action, Risk
            action = Action("run_command", "cwd test",
                            "Execute allowlisted command: python -c import os; print(os.getcwd())",
                            "workspace cwd", Risk.MEDIUM)
            guard.approve(guard.action_id(action))
            result = executor.run(
                ["python", "-c", "import os; print(os.getcwd())"],
                reason="cwd test", evidence="workspace cwd"
            )
            self.assertEqual(Path(result.stdout.strip()).resolve(), Path(tmp).resolve())

    def test_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, guard = self._executor(tmp, allowed_commands={"python"}, max_output_chars=20)
            from rooster_engine.guard import Action, Risk
            action = Action("run_command", "output test",
                            "Execute allowlisted command: python -c print('x'*100)",
                            "bounded stdout", Risk.MEDIUM)
            guard.approve(guard.action_id(action))
            result = executor.run(["python", "-c", "print('x'*100)"],
                                  reason="output test", evidence="bounded stdout")
            self.assertEqual(len(result.stdout), 20)

    def test_timeout_is_reported_and_counts_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget = RuntimeBudget(RuntimeLimits(max_steps=2, max_failures=1))
            executor, guard = self._executor(tmp, allowed_commands={"python"},
                                              budget=budget, timeout_seconds=0.05)
            from rooster_engine.guard import Action, Risk
            action = Action("run_command", "timeout test",
                            "Execute allowlisted command: python -c import time; time.sleep(1)",
                            "timeout evidence", Risk.MEDIUM)
            guard.approve(guard.action_id(action))
            result = executor.run(["python", "-c", "import time; time.sleep(1)"],
                                  reason="timeout test", evidence="timeout evidence")
            self.assertTrue(result.timed_out)
            self.assertEqual(budget.failures, 1)

    def test_git_is_not_allowlisted_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, _ = self._executor(tmp)
            with self.assertRaises(PermissionError):
                executor.run(["git", "push"], reason="test", evidence="denial")

    def test_emergency_stop_blocks_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor, guard = self._executor(tmp, allowed_commands={"python"})
            guard.emergency_stop.stop()
            with self.assertRaises(RuntimeError):
                executor.run(["python", "-c", "print('blocked')"],
                             reason="stop test", evidence="blocked")
