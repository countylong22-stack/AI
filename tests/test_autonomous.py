import json
import tempfile
import unittest
from pathlib import Path

from rooster_engine.autonomous import AutonomousCoder
from rooster_engine.core import AutonomousEngineer


class FakeResponse:
    def __init__(self, text):
        self.output_text = text


class FakeClient:
    def __init__(self):
        self.calls = 0

    class Responses:
        pass

    def _response(self, payload):
        return FakeResponse(json.dumps(payload))


class FakeResponsesClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.responses = self

    def create(self, **kwargs):
        self.calls += 1
        prompt = kwargs["input"]
        if "Return ONLY JSON" in prompt and '"read_paths"' in prompt:
            return self._response({"read_paths": ["sample.txt"], "approach": "update sample"})
        if '"patches"' in prompt:
            return self._response({
                "patches": [{"path": "sample.txt", "content": "updated\n"}],
                "intent": "update sample",
            })
        return self._response({"summary": "done"})


class AutonomousCoderTests(unittest.TestCase):
    def test_autonomous_write_is_guarded_and_tested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.txt").write_text("old\n", encoding="utf-8")
            engineer = AutonomousEngineer(root, root / "tasks.json")
            client = FakeResponsesClient()
            coder = AutonomousCoder(engineer, client=client, max_iterations=1)
            result = coder.run("update sample", task_id="test-task")
            self.assertEqual(result.status, "completed")
            self.assertEqual((root / "sample.txt").read_text(encoding="utf-8"), "updated\n")
            self.assertGreaterEqual(client.calls, 3)
            audit = (root / ".rooster" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("autonomous_task_completed", audit)
            self.assertIn("project_file_written", audit)

    def test_autonomous_cannot_write_protected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engineer = AutonomousEngineer(root, root / "tasks.json")
            action = engineer.guard.action_id(
                __import__("rooster_engine.guard", fromlist=["Action"]).Action(
                    "write_project_file",
                    "test",
                    "write protected",
                    "denied",
                    __import__("rooster_engine.guard", fromlist=["Risk"]).Risk.MEDIUM,
                    "rooster_engine/guard.py",
                )
            )
            engineer.guard.approve(action, actor="autonomous", task_id="test-task")
            with self.assertRaises(PermissionError):
                engineer.tools.run(
                    "write_project_file",
                    "rooster_engine/guard.py",
                    "bad",
                    reason="test",
                    action="write protected",
                    evidence="denied",
                    risk=__import__("rooster_engine.guard", fromlist=["Risk"]).Risk.MEDIUM,
                    target="rooster_engine/guard.py",
                    actor="autonomous",
                    task_id="test-task",
                )


if __name__ == "__main__":
    unittest.main()
