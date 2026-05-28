"""api/server.py — Dev Agent 入口
启动 UI:   streamlit run api/server.py
启动 API:  uv run langgraph dev --port 8003
"""
from langsmith import traceable
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis import RedisSaver
from shared.configs.settings import REDIS_URL, GRAPH_CONFIG
from graph.workflow import build_graph
from ui.streamlit_app import run_ui


@traceable
def run() -> None:
    with RedisSaver.from_conn_string(REDIS_URL) as cp:
        cp.setup()
        agent = build_graph().compile(checkpointer=cp)
        # run_ui(agent)
        result = agent.invoke(HumanMessage(content="这个月股票涨的比较厉害的10支股票，列出来"), config=GRAPH_CONFIG)
        print(result)


def clear_checkpoint():
    from redis import Redis
    r = Redis.from_url(REDIS_URL)
    keys = r.keys("checkpoint:*")
    if keys:
        r.delete(*keys)
        print(f"✅ 已清除 {len(keys)} 个 checkpoint 键")


# LangGraph CLI 识别此变量



# with RedisSaver.from_conn_string(REDIS_URL) as _cp:
#     _cp.setup()
#     graph = build_graph().compile(checkpointer=_cp)


if __name__ == "__main__":
    # clear_checkpoint()
    run()
