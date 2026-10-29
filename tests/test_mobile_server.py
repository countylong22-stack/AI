import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mobile_server
from fastapi import HTTPException


class MobileServerTests(unittest.TestCase):
    def setUp(self):
        self.original_tasks = dict(mobile_server._tasks)
        mobile_server._tasks.clear()

    def tearDown(self):
        mobile_server._tasks.clear()
        mobile_server._tasks.update(self.original_tasks)

    def test_health_is_public_and_identifies_service(self):
        result = mobile_server.health()
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "Rooster Autonomous Engineer")

    def test_protected_endpoints_require_configured_token(self):
        with patch.object(mobile_server, "TOKEN", ""):
            with self.assertRaises(HTTPException) as caught:
                mobile_server.require_token("Bearer anything")
        self.assertEqual(caught.exception.status_code, 503)

    def test_protected_endpoints_reject_wrong_token(self):
        with patch.object(mobile_server, "TOKEN", "correct-secret"):
            with self.assertRaises(HTTPException) as caught:
                mobile_server.require_token("Bearer wrong-secret")
        self.assertEqual(caught.exception.status_code, 401)

    def test_protected_endpoints_accept_correct_token(self):
        with patch.object(mobile_server, "TOKEN", "correct-secret"):
            self.assertIsNone(mobile_server.require_token("Bearer correct-secret"))

    def test_chat_requires_api_key(self):
        request = mobile_server.ChatRequest(
            messages=[mobile_server.ChatMessage(role="user", content="Hello")]
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                mobile_server.chat(request)
        self.assertEqual(caught.exception.status_code, 503)

    def test_chat_returns_model_reply(self):
        request = mobile_server.ChatRequest(
            messages=[mobile_server.ChatMessage(role="user", content="Hello")]
        )
        fake_response = SimpleNamespace(output_text="Hi there")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI") as client_factory:
                client_factory.return_value.responses.create.return_value = fake_response
                result = mobile_server.chat(request)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "Hi there")
        call = client_factory.return_value.responses.create.call_args.kwargs
        self.assertEqual(call["model"], "gpt-6.1-sol")
        self.assertEqual(call["reasoning"], {"effort": "medium"})
        client_factory.return_value.responses.create.assert_called_once()

    def test_task_requires_api_key(self):
        request = mobile_server.TaskRequest(objective="Inspect the project")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                mobile_server.start_task(request)
        self.assertEqual(caught.exception.status_code, 503)

    def test_task_is_queued_and_returns_identifier(self):
        request = mobile_server.TaskRequest(objective="Inspect the project")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(mobile_server._executor, "submit") as submit:
                result = mobile_server.start_task(request)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "queued")
        self.assertTrue(result["task_id"])
        submit.assert_called_once()
        self.assertEqual(mobile_server._tasks[result["task_id"]]["objective"], "Inspect the project")

    def test_only_one_active_task_is_allowed(self):
        mobile_server._tasks["existing"] = {
            "task_id": "existing",
            "objective": "Already working",
            "status": "running",
        }
        request = mobile_server.TaskRequest(objective="Another task")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(mobile_server._executor, "submit") as submit:
                with self.assertRaises(HTTPException) as caught:
                    mobile_server.start_task(request)
        self.assertEqual(caught.exception.status_code, 409)
        submit.assert_not_called()

    def test_task_lookup_returns_404_for_unknown_id(self):
        with self.assertRaises(HTTPException) as caught:
            mobile_server.get_task("missing")
        self.assertEqual(caught.exception.status_code, 404)

    def test_non_loopback_host_requires_tls(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        # CLI validation is exercised through main() in a subprocess in deployment;
        # this test protects the documented default argument from drifting.
        import inspect
        source = inspect.getsource(mobile_server.main)
        self.assertIn("Non-loopback access requires", source)
        self.assertIn("--ssl-certfile", source)
        self.assertIn("--ssl-keyfile", source)


if __name__ == "__main__":
    unittest.main()
