"""
ui/streamlit_app.py
Streamlit 前端：对话 + 侧边栏知识库管理 + RAGAS 评估历史。
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

    # ── 侧边栏 ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 配置")
        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.session_state.ragas_history = []
            st.rerun()

        # ── 知识库上传 ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("📚 本地知识库")
        uploaded = st.file_uploader(
            "上传文件（PDF / txt / md）",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("📥 写入知识库"):
            paths = []
            for f in uploaded:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(f.name).suffix)
                tmp.write(f.read()); tmp.close()
                paths.append(tmp.name)
            with st.spinner("Embedding 中..."):
                n = ingest_local_files(paths)
            st.success(f"✅ 已写入 {n} chunks（{len(uploaded)} 个文件）")

        # ── RAGAS 评估历史 ────────────────────────────────────────────────────
        st.divider()
        st.subheader("📊 RAGAS 评估")

        history = st.session_state.ragas_history
        if not history:
            st.caption("对话结束后自动评估，结果显示在这里")
        else:
            # 最新一条醒目展示
            latest = history[-1]
            col1, col2 = st.columns(2)
            with col1:
                _metric_card("Faithfulness",     latest.get("faithfulness"))
            with col2:
                _metric_card("Answer Relevancy", latest.get("answer_relevancy"))

            if latest.get("error"):
                st.warning(f"评估异常: {latest['error']}")

            # 历史趋势（多轮时展示）
            if len(history) > 1:
                with st.expander(f"📈 历史趋势（共 {len(history)} 轮）"):
                    import pandas as pd
                    df = pd.DataFrame([
                        {
                            "轮次":           i + 1,
                            "问题":           h.get("question", ""),
                            "faithfulness":  h.get("faithfulness"),
                            "answer_relevancy": h.get("answer_relevancy"),
                            "时间":           h.get("timestamp", ""),
                        }
                        for i, h in enumerate(history)
                    ])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.line_chart(
                        df[["faithfulness", "answer_relevancy"]].dropna(),
                        use_container_width=True,
                    )


def _metric_card(label: str, value: float | None) -> None:
    """简单的分数卡片，自动根据分数上色。"""
    if value is None:
        st.metric(label, "—")
        return
    pct = f"{value:.0%}"
    color = "🟢" if value >= 0.8 else ("🟡" if value >= 0.6 else "🔴")
    st.metric(label, f"{color} {pct}")
