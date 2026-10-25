"""Show a fixed report workflow using real graph/tools and no model API calls."""

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


class ReportDemoModel:
    """A scripted model adapter; it does not understand arbitrary user questions."""

    def __init__(self):
        self.step = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage, ToolMessage
        self.step += 1
        if self.step == 1:
            return AIMessage(content="准备合成演示报告。", tool_calls=[{
                "name": "fill_context_for_report", "args": {}, "id": "demo-switch", "type": "tool_call"}])
        if self.step == 2:
            return AIMessage(content="查询示例用户1001在2025-01的记录。", tool_calls=[{
                "name": "fetch_external_data", "args": {"user_id": "1001", "month": "2025-01"},
                "id": "demo-record", "type": "tool_call"}])
        record_message = next(message for message in reversed(messages)
                              if isinstance(message, ToolMessage) and message.name == "fetch_external_data")
        record = json.loads(record_message.content)
        text = "# 合成演示报告\n\n用户：1001；月份：2025-01\n\n"
        text += "\n".join(f"- {key}：{value}" for key, value in record.items())
        return AIMessage(content=text)


def run_demo():
    """Use a nonfunctional credential only to construct unused provider adapters."""
    os.environ["OPENAI_API_KEY"] = "example"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    sys.path.insert(0, str(ROOT))
    from agent.react_agent import ReactAgent
    return list(ReactAgent(model=ReportDemoModel()).execute_stream("固定合成报告演示"))


def main():
    for event in run_demo():
        print(f"[{event['type']}] {event['content']}")


if __name__ == "__main__":
    main()
