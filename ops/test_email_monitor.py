import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import email_monitor as monitor


class EmailMonitorTests(unittest.TestCase):
    def test_telegram_request(self):
        response = io.BytesIO(b'{"ok":true}')
        response.status = 200
        with patch.object(monitor.request, "urlopen", return_value=response) as mocked:
            self.assertTrue(monitor.send_telegram("test-token", "test-chat", "alert"))
        sent = mocked.call_args.args[0]
        self.assertEqual(sent.get_method(), "POST")
        self.assertIn(b"chat_id=test-chat", sent.data)
        self.assertIn(b"text=alert", sent.data)

    def test_telegram_failure_is_not_acknowledged(self):
        with patch.object(monitor.request, "urlopen", side_effect=OSError("offline")):
            self.assertFalse(monitor.send_telegram("test-token", "test-chat", "alert"))

    def test_api_alert_deduplicates_and_recovers(self):
        state = {"active": {}, "seen_failed_ids": []}
        messages = []
        def send(message):
            messages.append(message)
            return True
        with patch.object(monitor, "diagnostic", return_value={"ok": False}):
            self.assertTrue(monitor.run_check("api", state, send, lambda: None))
            self.assertTrue(monitor.run_check("api", state, send, lambda: None))
        with patch.object(monitor, "diagnostic", return_value={"ok": True}):
            self.assertTrue(monitor.run_check("api", state, send, lambda: None))
        self.assertEqual(len(messages), 2)
        self.assertIn("RECUPERADO", messages[-1])

    def test_state_transitions(self):
        state = {"active": {}, "seen_failed_ids": []}
        messages = []
        def send(message):
            messages.append(message)
            return True

        payload = {"ok": True, "failed_ids": [4], "overdue_count": 2,
                   "abandoned_count": 1}
        with patch.object(monitor, "worker_running", return_value=False), patch.object(
            monitor, "diagnostic", return_value=payload
        ):
            self.assertTrue(monitor.run_check("outbox", state, send, lambda: None))
            self.assertTrue(monitor.run_check("outbox", state, send, lambda: None))
        self.assertEqual(len(messages), 4)  # worker, failed, overdue, abandoned
        self.assertEqual(state["seen_failed_ids"], [4])
        payload = {"ok": True, "failed_ids": [4], "overdue_count": 0,
                   "abandoned_count": 0}
        with patch.object(monitor, "worker_running", return_value=True), patch.object(
            monitor, "diagnostic", return_value=payload
        ):
            self.assertTrue(monitor.run_check("outbox", state, send, lambda: None))
        self.assertEqual(len(messages), 7)
        self.assertTrue(all("RECUPERADO" in item for item in messages[4:]))

    def test_failed_telegram_retries_same_incident(self):
        state = {"active": {}, "seen_failed_ids": []}
        payload = {"ok": True, "failed_ids": [8], "overdue_count": 0,
                   "abandoned_count": 0}
        with patch.object(monitor, "worker_running", return_value=True), patch.object(
            monitor, "diagnostic", return_value=payload
        ):
            self.assertFalse(monitor.run_check("outbox", state, lambda message: False,
                                               lambda: None))
            self.assertEqual(state["seen_failed_ids"], [])
            self.assertTrue(monitor.run_check("outbox", state, lambda message: True,
                                              lambda: None))
            self.assertEqual(state["seen_failed_ids"], [8])

    def test_query_failure_alerts_once_and_recovers(self):
        state = {"active": {}, "seen_failed_ids": []}
        messages = []
        def send(message):
            messages.append(message)
            return True
        with patch.object(monitor, "worker_running", return_value=True), patch.object(
            monitor, "diagnostic", return_value=None
        ):
            monitor.run_check("outbox", state, send, lambda: None)
            monitor.run_check("outbox", state, send, lambda: None)
        with patch.object(monitor, "worker_running", return_value=True), patch.object(
            monitor, "diagnostic", return_value={"ok": True, "failed_ids": [],
                                                   "overdue_count": 0, "abandoned_count": 0}
        ):
            monitor.run_check("outbox", state, send, lambda: None)
        self.assertEqual(len(messages), 2)
        self.assertIn("RECUPERADO", messages[-1])

    def test_state_file_is_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            monitor.save_state(path, {"active": {"api": True}, "seen_failed_ids": [3]})
            self.assertEqual(monitor.load_state(path)["seen_failed_ids"], [3])
            self.assertEqual(json.loads(path.read_text())["active"], {"api": True})

    def test_config_requires_private_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "monitor.env"
            path.write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_ID=123\n")
            with patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=0o100600)):
                self.assertEqual(monitor.read_config(path), ("test-token", "123"))
            with patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=0o100644)):
                with self.assertRaises(ValueError):
                    monitor.read_config(path)


if __name__ == "__main__":
    unittest.main()
