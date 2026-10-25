"""Exercise Streamlit's real test runtime with deterministic application events."""

from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
import agent.react_agent as agent_module


APP = Path(__file__).resolve().parents[1] / "app.py"


class UiTests(unittest.TestCase):
    def test_chat_keeps_final_answer_outside_status_and_in_history(self):
        fake = Mock()
        fake.execute_stream.return_value = iter([
            {"type": "thought", "content": "查询示例资料"},
            {"type": "log", "content": "检索完成"},
            {"type": "answer", "content": "合成回答正文"},
        ])
        with patch.object(agent_module, "ReactAgent", return_value=fake):
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("test question").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["message"][-1], {"role": "assistant", "content": "合成回答正文"})
        self.assertTrue(any(element.value == "合成回答正文" for element in app.markdown))

    def test_error_event_remains_visible_without_a_fake_answer(self):
        fake = Mock()
        fake.execute_stream.return_value = iter([{"type": "error", "content": "synthetic failure"}])
        with patch.object(agent_module, "ReactAgent", return_value=fake):
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("test error").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.error[0].value, "synthetic failure")
        self.assertEqual(len(app.session_state["message"]), 1)
