"""
main.py
应用入口。根据运行方式选择 Streamlit UI 或命令行模式。

Streamlit：  streamlit run main.py
命令行测试：  python main.py
数据 ingest：python -m rag.ingest docs/resume.pdf docs/jd.md
"""
from langsmith import traceable
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis import RedisSaver

from src.configs.settings import REDIS_URL, GRAPH_CONFIG
from graph.workflow import build_graph
from ui.streamlit_app import run_ui


@traceable
def run() -> None:
    with RedisSaver.from_conn_string(REDIS_URL) as cp:
        cp.setup()
        agent = build_graph().compile(checkpointer=cp)

        # ── Streamlit UI（默认）────────────────────────────────────────────
        run_ui(agent)

        # ── 命令行测试（取消注释以使用）────────────────────────────────────
        # reply = agent.invoke(
        #     {
        #         "messages":       [HumanMessage(content="帮我指定一个减肥计划")],
        #         "reflections":    [],
        #         "human_feedback": "",
        #     },
        #     config=GRAPH_CONFIG,
        # )
        # print(reply.get("final_answer", reply["messages"][-1].content))

if __name__ == "__main__":
    run()