"""
ui/streamlit_app.py
Streamlit 前端：对话界面 + 侧边栏知识库管理。
入口：main.py 调用 run_ui(agent)。
"""
import tempfile
from pathlib import Path

import streamlit as st
from langchain_core.messages import HumanMessage

from config.settings import GRAPH_CONFIG
from rag.ingest import ingest_local_files


def run_ui(agent) -> None:
    st.title("🤖 DevAgent — Multi-Agent RAG 助手")
    st.caption("RAG 知识库 + 实时搜索缓存 | Supervisor 多 Agent 协作")

    if "messages" not in st.session_state:
        st.session_state.messages = []

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
                    },
                    config=GRAPH_CONFIG,
                )
                final = result.get("final_answer", result["messages"][-1].content)
                st.markdown(final)

                if result.get("reflections"):
                    with st.expander("🤔 系统反思"):
                        for r in result["reflections"]:
                            st.write(r)

        st.session_state.messages.append({"role": "assistant", "content": final})

    # ── 侧边栏：知识库管理 ────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 配置")

        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.subheader("📚 本地知识库")
        st.caption("支持 PDF / txt / md，写入后可被 Researcher Agent 检索")

        uploaded = st.file_uploader(
            "上传文件",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("📥 写入知识库"):
            paths = []
            for f in uploaded:
                suffix = Path(f.name).suffix
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(f.read())
                tmp.close()
                paths.append(tmp.name)
            with st.spinner("Embedding 中，请稍候..."):
                n = ingest_local_files(paths)
            st.success(f"✅ 已写入 {n} 个 chunks（{len(uploaded)} 个文件）")
