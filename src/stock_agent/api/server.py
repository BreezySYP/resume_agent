"""api/server.py — Stock Agent LangGraph 入口
langgraph.json 通过 `./api/server.py:graph` 加载图定义。
"""
from agent.graph import build_investment_agent
from langgraph.checkpoint.redis import RedisSaver
from shared.configs.settings import REDIS_URL

with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
    checkpointer.setup()
    graph = build_investment_agent(checkpointer=checkpointer)
