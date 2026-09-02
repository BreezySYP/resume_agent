"""stock_etl/main.py — Stock ETL API 入口"""
from router import etl_router
from shared.web.app import create_app

app = create_app(
    title="Stock ETL API",
    description="A股数据 ETL API：触发单股或全量数据采集，SSE 实时进度推送。",
    version="0.1.0",
    service_name="stock-etl-api",
    routers=[etl_router.router],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8011, reload=True, log_config=None)
