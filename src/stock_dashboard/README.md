# stock_dashboard

A 股 ETL 管理后台 API：股票数据查询、ETL 任务触发与断点状态管理。

## 运行

```bash
cd src/stock_dashboard
uv run uvicorn main:app --host 0.0.0.0 --port 8010
```

Swagger 文档：<http://localhost:8010/docs>

> 当前未包含在 `docker-compose.yml` 中，本地开发直接以 `uvicorn` 启动。

## API

### 股票数据（`/api/stocks`）

- `GET /api/stocks`：股票列表
- `GET /api/stocks/{code}`：单股详情
- `GET /api/stocks/status/overview`：全局 ETL step 状态概览

### ETL 任务（`/api/etl`）

- `GET /api/etl/steps`：所有可用 step 定义
- `GET /api/etl/jobs/running`：当前运行中的任务
- `GET /api/etl/jobs/logs`：任务历史日志
- `DELETE /api/etl/jobs/{job_id}`：取消 / 删除任务记录

### 状态（`/api/status`）

- `GET /api/status/checkpoints`：所有 step 的 checkpoint 状态
- `GET /api/status/checkpoints/{step}`：指定 step 的 checkpoint
- `DELETE /api/status/checkpoints/{step}`：清除指定 step 的 checkpoint
- `GET /api/status/summary`：ETL 整体健康状态

## 依赖

- MySQL（股票数据 / checkpoint）、Redis（任务状态）；配置统一读取仓库根 `.env`
