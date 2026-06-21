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
