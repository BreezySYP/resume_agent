"""api/server.py — Dev Agent 入口
启动 API: uv run langgraph dev --port 8003（langgraph.json 引用 ./api/server.py:graph）
启动 UI:  python -m api.server
"""
from graph.workflow import build_graph
from langgraph.checkpoint.redis import RedisSaver
from shared.configs.settings import REDIS_URL
from ui.streamlit_app import run_ui

with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
    checkpointer.setup()
    graph = build_graph().compile(checkpointer=checkpointer)

if __name__ == "__main__":
    run_ui(graph)
