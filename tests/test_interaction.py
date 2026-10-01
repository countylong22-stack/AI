import tempfile
import unittest
from pathlib import Path

from rooster_engine.core import ToolRegistry
from rooster_engine.guard import Action, Risk, RoosterGuard
from rooster_engine.interaction import parse_chat_action


class ChatInteractionTests(unittest.TestCase):
    def test_run_test_suite_request_creates_exact_guarded_action(self):
        action = parse_chat_action("Rooster, I want you to run the test suite.")
        self.assertEqual(
            action,
            Action(
                tool="run_tests",
                reason="User explicitly requested the repository test suite from the interactive chat.",
                action="Run the fixed repository unittest discovery suite",
                evidence="Repository test-suite output and exit status",
                risk=Risk.MEDIUM,
                target="tests",
            ),
        )

    def test_unrecognized_request_does_not_create_action(self):
        self.assertIsNone(parse_chat_action("Tell me what you found."))

    def test_approved_chat_action_is_context_bound_and_one_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = RoosterGuard(root, root / "audit.jsonl")
            registry = ToolRegistry(guard)
            calls = []
            registry.register("run_tests", lambda: calls.append("ran") or "ok")

            action = parse_chat_action("run the test suite")
            action_id = guard.action_id(action)
            guard.approve(action_id, actor="human", task_id="chat-test-123")

            result = registry.run(
                "run_tests",
                reason=action.reason,
                action=action.action,
                evidence=action.evidence,
                risk=action.risk,
                target=action.target,
                actor="human",
                task_id="chat-test-123",
            )

            self.assertEqual(result, "ok")
            self.assertEqual(calls, ["ran"])
            with self.assertRaises(PermissionError):
                registry.run(
                    "run_tests",
                    reason=action.reason,
                    action=action.action,
                    evidence=action.evidence,
                    risk=action.risk,
                    target=action.target,
                    actor="human",
                    task_id="chat-test-123",
                )


if __name__ == "__main__":
    unittest.main()
