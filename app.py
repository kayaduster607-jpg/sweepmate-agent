import time
import streamlit as st
from agent.react_agent import ReactAgent

st.set_page_config(page_title="SweepMate Agent")
st.title("SweepMate Agent · 扫地机器人智能客服")
st.caption("学习演示：天气、身份、位置与月份工具为模拟实现，示例记录为合成数据。")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

# 1. 渲染历史消息
for message in st.session_state["message"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input()

if prompt:
    # 2. 显示用户提问
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    # 3. 准备生成回复
    with st.chat_message("assistant"):

        # --- UI 布局关键点 ---
        # A. 先创建“思考过程”的折叠容器
        # state="running" 会显示转圈动画
        status_container = st.status("正在检索和执行工具...", expanded=True)

        # B. 【关键】在折叠容器 *外面* 创建一个空的占位符，用于显示最终结果
        # 这样无论折叠框是开是关，结果都会打印在框的下面，不会被吞掉
        answer_placeholder = st.empty()

        # C. 准备数据流
        res_stream = st.session_state["agent"].execute_stream(prompt)
        full_response = ""  # 用于存储完整的最终答案
        thought_buffer = ""  # 用于存储思考过程日志
        had_error = False

        # 4. 开始流式循环
        for chunk in res_stream:

            # Case 1: 思考过程 / 工具日志
            if chunk["type"] in ["thought", "log"]:
                # 往折叠框里写
                thought_buffer += chunk["content"] + "\n\n"
                status_container.markdown(thought_buffer)

            # Case 2: 最终答案 (Answer)
            elif chunk["type"] == "answer":
                # 第一次收到答案时，关闭思考框，标记为成功
                status_container.update(label="执行完成 (点击展开查看过程)", state="complete", expanded=False)

                # 累加答案 (防止分段输出导致覆盖)
                new_text = chunk["content"]
                full_response += new_text

                # 更新 *外部* 的占位符，模拟打字机
                # 注意：这里我们更新的是 answer_placeholder，它在 status_container 外面
                answer_placeholder.markdown(full_response + "▌")
                time.sleep(0.005)  # 稍微给点视觉延迟

            # Case 3: 错误
            elif chunk["type"] == "error":
                had_error = True
                status_container.update(label="发生错误", state="error", expanded=True)
                st.error(chunk["content"])

        # 5. 循环结束
        # 去掉最后的光标
        if full_response:
            answer_placeholder.markdown(full_response)
        elif not had_error:
            # 如果跑完了全流程却没说话 (比如只跑了工具)，给个提示
            status_container.update(label="执行完毕", state="complete", expanded=False)
            if not full_response:
                answer_placeholder.warning("任务已完成，但没有生成文本回复。")

    # 6. 保存到历史记录 (只存最终结果，清爽)
    if full_response:
        st.session_state["message"].append({"role": "assistant", "content": full_response})
