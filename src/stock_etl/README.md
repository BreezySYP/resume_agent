# stock_etl

A 股股票数据 ETL：抓取行情 / 财报 / 资讯 → 计算因子 → 写入 MySQL / Qdrant。
`stock_agent` 只负责 Agent 推理与检索，所有数据采集和因子计算都在本项目完成。

## 目录结构

```text
stock_etl/
├── sources/            # 数据源抓取（history / tick / news / profile / financial_statement / capital_and_hot）
├── factors/            # 纯函数式因子计算（technical / financial_feature / financial_factor / composite）
├── services/           # 编排层：pipeline_single_stock.py（各 step 实现）、etl_service.py（任务触发）、data_loader.py
├── storage/            # 写入层（mysql_writer.py）+ 断点续跑（step_checkpoint.py / code_checkpoint.py）
├── research/           # 因子回测与诊断（非每日例行任务）
├── router/             # FastAPI 路由（etl_router.py）
├── main.py             # API 入口
├── constants.py        # step 定义（STEPS_META / DAILY_STEPS / SEASON_STEPS）
└── schema.sql          # MySQL 建表语句
```

## 运行

### API（推荐入口）

```bash
cd src/stock_etl
uv run uvicorn main:app --host 0.0.0.0 --port 8011
```

Swagger 文档：<http://localhost:8011/docs>

### API 端点

- `POST /api/etl/trigger/stock`：触发单股一个或多个 step（`code` + `steps`）。
- `POST /api/etl/trigger/all`：触发全量 ETL，`mode=daily`（每日）或 `mode=season`（含季报财务因子），
  也可用 `steps` 自定义。
- `GET /api/etl/steps`：列出所有可用 step 定义与分组。
- `GET /api/etl/stream/{job_id}`：SSE 订阅任务实时进度。

```bash
curl -X POST http://localhost:8011/api/etl/trigger/all \
  -H 'Content-Type: application/json' -d '{"mode": "daily"}'
```

## Steps

定义在 `constants.py`：

- daily：`history` `technical` `capital_hot` `profile` `news` `qdrant_profile_sync` `qdrant_news_sync`
- season：在 daily 基础上增加 `financial_statement` `financial_feature` `financial_factor` `composite`
- 单股可触发（`PER_STOCK_STEPS`）：`history` `financial_statement` `profile` `news`

各 step 的具体实现位于 `services/pipeline_single_stock.py`，可按需直接 import 调用。

## 断点续跑（etl_checkpoint）

`schema.sql` 中的 `etl_checkpoint` 表按 `step` 记录 `start_date` / `start_code`，
逐代码扫描类 step 每处理完一只股票就写入断点；进程崩溃后重跑同一 step 会从断点继续。

- `history`：跑完一轮后 `start_date` 推进到本次 `end_date`，下次默认拉增量。
- `financial_statement` / `profile` / `news`：跑完一轮全市场后清空断点，下次从头全量刷新。

读写封装在 `storage/step_checkpoint.py`（`get_checkpoint` / `save_checkpoint` / `clear_checkpoint`）和
`storage/code_checkpoint.py`（按股票代码断点）。

## 依赖

- MySQL（写入 / 断点）、Redis（SSE 事件队列）、Qdrant（向量同步）、akshare / baostock（数据源）
- 配置统一读取仓库根 `.env`，见 `.env.example` 模板
