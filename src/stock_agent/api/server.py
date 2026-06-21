"""api/server.py — Stock Agent 入口
启动: uv run langgraph dev --port 8004
"""
import sys

from agent.graph import build_investment_agent
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis import RedisSaver
from shared.configs.settings import REDIS_URL

load_dotenv()

with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
    checkpointer.setup()
    graph = build_investment_agent(checkpointer=checkpointer)

if __name__ == "__main__":
    _graph = build_investment_agent()
    question = sys.argv[1] if len(sys.argv) > 1 else "这个月涨幅比例最高的10支股票"
    result = _graph.invoke({"messages": [HumanMessage(content=question)], "user_question": question})
    print(result["final_answer"])
