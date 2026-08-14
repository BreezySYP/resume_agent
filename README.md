# 金融 Agent Monorepo

A 股投研多 Agent 系统 monorepo：数据 ETL → 因子计算 → 向量检索 → LangGraph Agent 分析 → 管理后台，
基于 [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) 管理，所有服务共用 `packages/shared`。

## 项目结构

| 项目 | 路径 | 说明 | 默认端口 |
| --- | --- | --- | --- |
| shared | `packages/shared` | 跨服务共用库（配置 / DB / 模型 / 检索 / 安全 / Web 工厂） | - |
| dev_agent | `src/dev_agent` | 多 Agent 编码助手（RAG 知识库 + RAGAS 评估） | 8003 API / 8501 UI |
| stock_agent | `src/stock_agent` | A 股智能投研 Agent（LangGraph 多节点分析 + SSE 推送） | 8004 |
| stock_etl | `src/stock_etl` | A 股数据 ETL：抓取 → 因子计算 → 写入 MySQL / Qdrant | 8011 |
| stock_dashboard | `src/stock_dashboard` | ETL 管理后台 API（任务触发 / 断点 / 股票查询） | 8010 |

## 快速开始

### 环境要求

- Python 3.11 + [uv](https://docs.astral.sh/uv/)
- 基础设施：redis / mysql / qdrant / minio（`docker-compose.yml` 已定义）

### 安装与验证

```bash
uv sync                        # 安装 workspace 全部依赖
uv run pytest                  # 全量测试
uv run ruff check packages/shared/src/shared/configs packages/shared/src/shared/web tests
```

### 本地启动

```bash
# stock_agent（Agent API）
cd src/stock_agent && uv run uvicorn main:app --host 0.0.0.0 --port 8004

# stock_etl（ETL API）
cd src/stock_etl && uv run uvicorn main:app --host 0.0.0.0 --port 8011

# stock_dashboard（管理后台）
cd src/stock_dashboard && uv run uvicorn main:app --host 0.0.0.0 --port 8010

# dev_agent（LangGraph API + Streamlit UI）
cd src/dev_agent && uv run langgraph dev --host 0.0.0.0 --port 8003
```

各服务详细用法见对应目录的 `README.md`。

### 容器化部署

```bash
# 先起基础设施
docker-compose up -d redis mysql qdrant minio
# 再起业务服务
docker-compose up -d dev-agent stock-agent stock_etl
```

## 配置

- `.env.example`：全部配置项模板，敏感键只放占位符，可提交到 git。
- `.env` / `.env.prod`：本地 / 生产配置，已被 gitignore（含真实密钥）。
- 优先级：**真实环境变量（容器 `-e` / compose `environment` / `env_file`） > `.env` 文件 > 代码默认值**。
- 统一入口：`packages/shared/src/shared/configs/settings.py`（pydantic-settings，`shared.configs.settings`）。

## 测试与质量

- 测试框架：pytest + pytest-cov；`tests/` 目录镜像 import 命名空间（`tests/shared/`、`tests/stock_agent/`）。
- 代码规范：ruff（E / F / I），CI 见 `.github/workflows/ci.yml`（lint + test）。
