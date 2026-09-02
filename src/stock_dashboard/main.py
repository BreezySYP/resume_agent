"""stock_dashboard/main.py — Stock Dashboard API 入口"""
from routers import etl, status, stocks
from shared.web.app import create_app

app = create_app(
    title="Stock Dashboard API",
    description="A股数据 ETL 管理后台 API：股票数据查询、ETL 任务触发与断点状态管理。",
    version="0.1.0",
    service_name="stock-dashboard-api",
    routers=[stocks.router, etl.router, status.router],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True, log_config=None)
