"""Run the actual LangGraph with scripted model messages and real tool execution."""

import unittest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from agent.react_agent import ReactAgent


class ScriptedModel:
    """Supply deterministic responses without contacting any model provider."""

    def __init__(self, responses):
        self.responses = iter(responses)
        self.inputs = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        self.inputs.append(list(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def call(name, args=None, identifier="call-1"):
    return {"name": name, "args": args or {}, "id": identifier, "type": "tool_call"}


class AgentTests(unittest.TestCase):
    def test_direct_answer_is_classified_without_tool_logs(self):
        agent = ReactAgent(model=ScriptedModel([AIMessage(content="合成回答")]))
        self.assertEqual(list(agent.execute_stream("hello")), [{"type": "answer", "content": "合成回答"}])

    def test_real_tool_node_executes_then_returns_to_agent(self):
        model = ScriptedModel([
            AIMessage(content="查询演示天气", tool_calls=[call("get_weather", {"city": "杭州"})]),
            AIMessage(content="以上是固定演示天气。"),
        ])
        events = list(ReactAgent(model=model).execute_stream("weather"))
        self.assertEqual([event["type"] for event in events], ["thought", "log", "answer"])
        self.assertIn("成功", events[1]["content"])
        tool_results = [message for message in model.inputs[1] if message.type == "tool"]
        self.assertIn("26", tool_results[0].content)

    def test_successful_report_switch_changes_the_next_system_prompt(self):
        model = ScriptedModel([
            AIMessage(content="准备演示报告", tool_calls=[call("fill_context_for_report")]),
            AIMessage(content="合成演示报告"),
        ])
        agent = ReactAgent(model=model)
        events = list(agent.execute_stream("report"))
        self.assertEqual(events[-1]["type"], "answer")
        self.assertIn("报告助手", model.inputs[1][0].content)
        state = agent.graph.get_state({"configurable": {"thread_id": "default_thread"}})
        self.assertTrue(state.values["is_report_mode"])

    def test_failed_report_tool_does_not_switch_prompt(self):
        @tool("fill_context_for_report", description="Synthetic failing report switch")
        def fail():
            raise RuntimeError("synthetic failure")

        model = ScriptedModel([
            AIMessage(content="prepare", tool_calls=[call("fill_context_for_report")]),
            AIMessage(content="工具未成功。"),
        ])
        agent = ReactAgent(model=model, tools=[fail])
        events = list(agent.execute_stream("report"))
        self.assertIn("失败", next(event["content"] for event in events if event["type"] == "log"))
        self.assertNotIn("报告助手", model.inputs[1][0].content)
        state = agent.graph.get_state({"configurable": {"thread_id": "default_thread"}})
        self.assertFalse(state.values["is_report_mode"])

    def test_explicit_threads_keep_separate_histories(self):
        model = ScriptedModel([AIMessage(content="A"), AIMessage(content="B"), AIMessage(content="A2")])
        agent = ReactAgent(model=model)
        list(agent.execute_stream("alpha", thread_id="a"))
        list(agent.execute_stream("beta", thread_id="b"))
        list(agent.execute_stream("alpha again", thread_id="a"))
        second = [m.content for m in model.inputs[1] if isinstance(m, HumanMessage)]
        third = [m.content for m in model.inputs[2] if isinstance(m, HumanMessage)]
        self.assertEqual(second, ["beta"])
        self.assertEqual(third, ["alpha", "alpha again"])

    def test_provider_failure_becomes_an_error_event(self):
        model = ScriptedModel([RuntimeError("synthetic provider failure")])
        events = list(ReactAgent(model=model).execute_stream("hello"))
        self.assertEqual(events[0]["type"], "error")
        self.assertIn("synthetic provider failure", events[0]["content"])
