"""stock_dashboard/main.py — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from api import agent_router
from shared.configs.log_config import setup_logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 启动 Stock Agent API")
    # init_db()
    setup_logger()
    logger.info("✅ 数据库表检查完成")
    yield
    logger.info("👋 Stock Agent API 关闭")


app = FastAPI(
    title="Stock Dashboard API",
    description="""
A股数据 ETL 管理后台 API。

## 功能模块

- **股票数据**：查看股票列表、单股详情（K线/新闻/财务/简介）
- **ETL 任务**：触发单股或全量数据下载，SSE 实时进度推送
- **ETL 状态**：查看 checkpoint 断点状态、任务执行历史

## 数据来源

底层复用 `stock_etl` 项目的 pipeline，通过 akshare / tushare 等包采集数据。
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：允许 React 前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境建议改成具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent_router.router)

@app.get("/", tags=["健康检查"], summary="服务健康检查")
def health_check():
    return {"status": "ok", "service": "stock-dashboard-api"}



from observe.metrics import metrics_response_body, metrics_content_type


@app.get("/metrics")
def metrics():
    return Response(
        content=metrics_response_body(),
        media_type=metrics_content_type(),
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8012, reload=True)