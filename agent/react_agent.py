import sys
import os
import operator
import traceback
import re
from typing import Annotated, Sequence, TypedDict, Literal

sys.path.append(os.getcwd())

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts, load_report_prompts
from utils.logger_handler import logger
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    is_report_mode: bool


class ReactAgent:
    def __init__(self, model=None, tools=None):
        self.tools = tools if tools is not None else [
            rag_summarize, get_weather, get_user_location, get_user_id,
            get_current_month, fetch_external_data, fill_context_for_report
        ]
        # Injection allows offline verification of the actual graph runtime.
        self.model_with_tools = (model if model is not None else chat_model).bind_tools(self.tools)

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self._execute_tools)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", self._should_continue, {"tools": "tools", "end": END})
        workflow.add_edge("tools", "agent")

        self.checkpointer = MemorySaver()
        self.graph = workflow.compile(checkpointer=self.checkpointer)

    def _call_model(self, state: AgentState):
        messages = state["messages"]
        is_report = state.get("is_report_mode", False)
        sys_prompt_str = load_report_prompts() if is_report else load_system_prompts()

        # 强制模型纯净输出
        sys_prompt_str += (
            "\n\n【OUTPUT RULES】\n"
            "1. NO emojis.\n"
            "2. NO raw JSON/XML.\n"
            "3. If using tools, state the plan briefly (e.g. 'Checking weather...').\n"
            "4. If answering the user, just give the answer directly. Do not repeat the question."
        )
        system_msg = SystemMessage(content=sys_prompt_str)
        history_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        prompt_messages = [system_msg] + history_messages
        response = self.model_with_tools.invoke(prompt_messages)
        return {"messages": [response]}

    def _execute_tools(self, state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_executor = ToolNode(self.tools)
        try:
            result = tool_executor.invoke({"messages": [last_message]})
            update_dict = {"messages": result["messages"]}
            for msg in result["messages"]:
                if (isinstance(msg, ToolMessage) and msg.name == "fill_context_for_report"
                        and getattr(msg, "status", "success") != "error"):
                    update_dict["is_report_mode"] = True
            return update_dict
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Resolve every pending tool call so the next model turn is valid.
            return {"messages": [ToolMessage(
                content="工具执行失败，请说明限制或尝试其他已提供的工具。",
                tool_call_id=call["id"], name=call["name"], status="error",
            ) for call in last_message.tool_calls]}

    def _should_continue(self, state: AgentState) -> Literal["tools", "end"]:
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
            return "tools"
        return "end"

    def _clean_content(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('}', '').replace('{', '').replace('PROCESSED', '')
        return text.strip()

    # --- 核心修改：精准分类逻辑 ---
    def execute_stream(self, query: str, thread_id: str = "default_thread"):
        input_state = {"messages": [HumanMessage(content=query)], "is_report_mode": False}
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}

        try:
            # stream_mode="updates" 保证我们拿到的是完整的消息对象
            for chunk in self.graph.stream(input_state, config=config, stream_mode="updates"):
                for node_name, updates in chunk.items():

                    # 1. Agent 节点的输出
                    if node_name == "agent":
                        latest_message = updates["messages"][-1]
                        content = self._clean_content(str(latest_message.content))

                        if content:
                            # 判据：如果这条消息里带着 tool_calls，说明它是“思考/计划”
                            if hasattr(latest_message, "tool_calls") and len(latest_message.tool_calls) > 0:
                                yield {"type": "thought", "content": content}
                            else:
                                # 否则，它是最终给用户的“答案”
                                yield {"type": "answer", "content": content}

                    # 2. Tools 节点的输出 (日志)
                    elif node_name == "tools":
                        if "messages" in updates:
                            for msg in updates["messages"]:
                                if isinstance(msg, ToolMessage):
                                    # 日志也是思考的一部分
                                    status = "失败" if getattr(msg, "status", "success") == "error" else "成功"
                                    log_text = (
                                        f"> [系统日志] 执行工具: {msg.name}  \n"
                                        f"> [系统日志] 执行状态: {status}"
                                    )
                                    yield {"type": "log", "content": log_text}

        except Exception as e:
            logger.error(traceback.format_exc())
            yield {"type": "error", "content": str(e)}
