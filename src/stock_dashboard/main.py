"""stock_dashboard/main.py — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from routers import stocks, etl, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 启动 Stock agent API")
    # init_db()
    logger.info("✅ 数据库表检查完成")
    yield
    logger.info("👋 Stock agent API 关闭")


app = FastAPI(
    title="Stock agent API",
    description="""
A股数据 ETL 管理后台 API。

## 功能模块

- 股票投资相关问题解答

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
app.include_router(stocks.router)
app.include_router(etl.router)
app.include_router(status.router)


@app.get("/", tags=["健康检查"], summary="服务健康检查")
def health_check():
    return {"status": "ok", "service": "stock-dashboard-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)