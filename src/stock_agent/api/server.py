"""api/server.py — Stock Agent 入口
启动: uv run langgraph dev --port 8004
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()


# print("LANGSMITH_API_KEY : " + os.getenv("LANGSMITH_API_KEY"))
# print("LANGSMITH_TRACING : " + os.getenv("LANGSMITH_TRACING"))
# print("LANGSMITH_ENDPOINT : " + os.getenv("LANGSMITH_ENDPOINT"))
# print("LANGCHAIN_PROJECT : " + os.getenv("LANGCHAIN_PROJECT"))

from langchain_core.messages import HumanMessage
from agent.graph import build_graph
from shared.agents.checkpoint import get_redis_checkpointer
# from fastapi import FastAPI
# from langserve import add_routes
# import uvicorn
from shared.configs.settings import REDIS_URL, GRAPH_CONFIG

from langgraph.checkpoint.redis import RedisSaver

# app = FastAPI()


# if __name__ == "__main__":
#     with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
#         checkpointer.setup()
#         graph = build_graph().compile()
#         add_routes(app, graph, path="/stock-agent")
#         uvicorn.run(app, host="0.0.0.0", port=8001)

with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
    checkpointer.setup()
    graph = build_graph().compile()

# from shared.configs.settings import REDIS_URL, GRAPH_CONFIG
# if __name__ == "__main__":
#     _graph   = build_graph().compile()
#     question = sys.argv[1] if len(sys.argv) > 1 else "这个月涨幅比例最高的10支股票"
#     result   = _graph.invoke({
#         "messages":        [HumanMessage(content=question)],
#         "user_question":   question,
#         "retry_count":     0,
#         "review_feedback": None,
#     })
#     print(result["final_answer"])