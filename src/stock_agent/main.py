"""stock_agent/main.py — Stock Agent API 入口"""
from api import agent_router, memory_router
from observe.metrics import metrics_content_type, metrics_response_body
from shared.web.app import create_app

app = create_app(
    title="Stock Agent API",
    description="A股智能投研 Agent：基于 LangGraph 的多节点分析流程，SSE 实时推送回答进度。",
    version="0.1.0",
    service_name="stock-agent-api",
    routers=[agent_router.router, memory_router.router],
    metrics_provider=lambda: (metrics_response_body(), metrics_content_type()),
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8013, reload=True)
