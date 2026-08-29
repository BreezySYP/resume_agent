"""ui/streamlit_app.py — Streamlit 前端"""
import tempfile
from pathlib import Path

import streamlit as st
from langchain_core.messages import HumanMessage
from rag.ingest import ingest_local_files
from shared.configs.settings import GRAPH_CONFIG


def run_ui(agent) -> None:
    st.title("🤖 DevAgent — Multi-Agent RAG 助手")
    st.caption("RAG 知识库 + 实时搜索缓存 | Supervisor 多 Agent 协作")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "ragas_history" not in st.session_state:
        st.session_state.ragas_history = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("请输入你的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Multi-Agent RAG 系统思考中..."):
                result = agent.invoke(
                    {"messages": [HumanMessage(content=prompt)],
                     "reflections": [], "human_feedback": "",
                     "ragas_result": None},
                    config=GRAPH_CONFIG,
                )
                final = result.get("final_answer", result["messages"][-1].content)
                st.markdown(final)
                if result.get("reflections"):
                    with st.expander("🤔 系统反思"):
                        for r in result["reflections"]:
                            st.write(r)
                if result.get("ragas_result"):
                    st.session_state.ragas_history.append(result["ragas_result"])

        st.session_state.messages.append({"role": "assistant", "content": final})

    with st.sidebar:
        st.header("📚 知识库管理")
        uploaded = st.file_uploader("上传文档", type=["pdf", "txt", "md"], accept_multiple_files=True)
        if uploaded and st.button("📥 导入到知识库"):
            with tempfile.TemporaryDirectory() as tmp:
                paths = []
                for f in uploaded:
                    p = Path(tmp) / f.name
                    p.write_bytes(f.read())
                    paths.append(str(p))
                n = ingest_local_files(paths)
                st.success(f"✅ 成功导入 {n} 个 chunks")

        if st.session_state.ragas_history:
            st.header("📊 RAGAS 评估历史")
            for r in st.session_state.ragas_history[-5:]:
                st.text(f"Q: {r.get('question', '')}")
                col1, col2 = st.columns(2)
                col1.metric("Faithfulness",     r.get("faithfulness"))
                col2.metric("Answer Relevancy", r.get("answer_relevancy"))

        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.rerun()
