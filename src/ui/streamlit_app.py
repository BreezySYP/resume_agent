"""
ui/streamlit_app.py
Streamlit 前端：对话 + 侧边栏知识库管理 + RAGAS 评估历史。
"""
import tempfile
from pathlib import Path

import streamlit as st
from langchain_core.messages import HumanMessage

from src.configs.settings import GRAPH_CONFIG
from src.rag.ingest import ingest_local_files


def run_ui(agent) -> None:
    print(" preparing UI...")
    st.title("🤖 DevAgent — Multi-Agent RAG 助手")
    st.caption("RAG 知识库 + 实时搜索缓存 | Supervisor 多 Agent 协作")

    if "messages"     not in st.session_state: st.session_state.messages     = []
    if "ragas_history" not in st.session_state: st.session_state.ragas_history = []

    # ── 历史消息 ──────────────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── 输入框 ────────────────────────────────────────────────────────────────
    if prompt := st.chat_input("请输入你的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Multi-Agent RAG 系统思考中..."):
                result = agent.invoke(
                    {
                        "messages":       [HumanMessage(content=prompt)],
                        "reflections":    [],
                        "human_feedback": "",
                        "rag_contexts":   [],
                        "ragas_result":   None,
                    },
                    config=GRAPH_CONFIG,
                )
                final = result.get("final_answer", result["messages"][-1].content)
                st.markdown(final)

                if result.get("reflections"):
                    with st.expander("🤔 系统反思"):
                        for r in result["reflections"]:
                            st.write(r)

                # 把本轮 RAGAS 结果存入历史
                if result.get("ragas_result"):
                    st.session_state.ragas_history.append(result["ragas_result"])

        st.session_state.messages.append({"role": "assistant", "content": final})

def _metric_card(label: str, value: float | None) -> None:
    """简单的分数卡片，自动根据分数上色。"""
    if value is None:
        st.metric(label, "—")
        return
    pct = f"{value:.0%}"
    color = "🟢" if value >= 0.8 else ("🟡" if value >= 0.6 else "🔴")
    st.metric(label, f"{color} {pct}")

