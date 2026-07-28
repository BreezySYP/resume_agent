# stock_etl

A 股股票数据 ETL：拉取行情/财报/资讯 → 计算因子 → 写入 MySQL / Qdrant。
`stock_agent` 只负责 Agent 推理与检索，所有数据采集和因子计算都在本项目完成。

## 目录结构

```
stock_etl/
├── sources/        # 数据源抓取（history/tick/news/profile/financial_statement/capital_and_hot）
├── factors/        # 纯函数式因子计算（technical / financial_feature / financial_factor / composite）
├── storage/        # 写入层（mysql_writer.py / qdrant_writer.py）
├── research/        # 因子回测与诊断（非每日例行任务）
├── data_loader.py  # 带本地 CSV 缓存的读取层，给 research/ 用
├── pipeline.py      # 唯一入口：组合 sources -> factors -> storage
└── schema.sql        # MySQL 建表语句
```

## 每日例行入口

```bash
# 默认: history -> technical -> composite
uv run python -m pipeline

# 自定义步骤
uv run python -m pipeline --steps history,technical,financial_feature,financial_factor,composite

# 全部步骤（含低频的 profile/news/financial_statement/qdrant_sync）
uv run python -m pipeline --steps all
```

可选 step：`history` `technical` `financial_feature` `financial_factor` `composite`
`capital_hot` `financial_statement` `profile` `news` `qdrant_sync`

- `financial_statement` / `profile` / `news`：低频抓取（建议按周/季度跑），数据量大、接口易触发频控。
- `qdrant_sync`：把 MySQL 中的新闻/主营业务画像同步到 Qdrant 混合向量库，供 `stock_agent` 检索。

## 通用代码归属

- 股票代码规则 (`add_prefix`/`remove_prefix`)、MySQL 连接池、Qdrant client、Redis 缓存装饰器、
  文本拼装函数等被 `stock_agent` 和 `stock_etl` 共用的代码统一放在 `packages/shared`。

## 断点续跑（etl_checkpoint）

`schema.sql` 新增了 `etl_checkpoint` 表，按 `step` 记录 `start_date` / `start_code`：

```sql
CREATE TABLE etl_checkpoint (
    step VARCHAR(50) PRIMARY KEY,
    start_date DATE,
    start_code VARCHAR(20),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

逐代码扫描类的 step（`history` `financial_statement` `profile` `news`）会在每只股票处理完后写入
`start_code`；进程中途崩溃后重新运行同一 step，会自动从断点继续，不用每次从代码 `000000` 重头跑。

- `history`：成功跑完一轮后会把 `start_date` 推进到本次的 `end_date`，下次默认从这里继续拉增量。
- `financial_statement` / `profile` / `news`：跑完一轮全市场后会清空断点，下次重新从头开始全量刷新。

读写封装在 `storage/checkpoint.py`：`get_checkpoint(step)` / `save_checkpoint(step, ...)` / `clear_checkpoint(step)`。
