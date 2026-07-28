What this is
一个以“代理 + 数据 ETL + 可视化”为中心的工具集合：把 A 股行情/财报/资讯抓取并计算因子存入 MySQL/Qdrant（stock_etl），提供基于检索与 LLM 推理的代理服务（stock_agent / dev_agent），并附带一个基于 FastAPI 的仪表盘（stock_dashboard）和若干实验型 Jupyter 笔记本。目标用户是做量化因子计算、数据工程与基于检索的代理原型验证的开发者与研究者。

Stack
Language(s): Jupyter Notebook (大量实验笔记本)、Python（服务与库）
Framework / runtime: Python + uvicorn / FastAPI-style server (uv run / uvicorn)，FastAPI（仪表盘），Jupyter Lab（交互式实验）
Notable libraries & infra:、uvicorn（ASGI server）、Qdrant（向量检索，qdrant 客户端）、MySQL（持久化）、Redis / MinIO（运行时依赖）。
Monitoring & tracing : `tempo `loki `grafana （具体依赖请参见docker-compose.yaml 以及各子项目的 pyproject.toml 与根目录的 .env.example）
How it's organized
Text
.devcontainer/        # 开发容器配置
.notebook/            # Jupyter 笔记本与实验脚本（notebook/*.ipynb, 9.py 等）
Dockerfile.*          # 各类容器镜像构建文件（dev-agent / stock-agent / stock_etl）
docker-compose.yml    # 启动依赖服务与容器的组合
entrypoint.sh         # 容器启动脚本
pyproject.toml        # 根项目依赖/配置（工作区级）
uv.lock               # 依赖锁
packages/             # 共享包（packages/shared：stock_etl 与 stock_agent 共享代码）
data/                 # 数据（示例、缓存、CSV 等）
src/
  dev_agent/          # 开发/演示用 agent（UI / graph / api）
  stock_agent/        # 代理服务：推理、检索、API 入口（main.py、service、store 等）
  stock_dashboard/    # FastAPI 仪表盘（main.py、routers、schemas.py）
  stock_etl/          # 数据 ETL：sources -> factors -> storage（pipeline.py, schema.sql, sources/, factors/）
.notable-scripts.sh   # 脚本：stock_api.sh / stock_agent_api.sh / stock_etl_api.sh
How it fits together:

ETL（src/stock_etl）按步骤从外部抓取行情/新闻/财报，计算因子并写入 MySQL 与 Qdrant（pipeline.py 为入口，schema.sql 定义表结构）。共享工具（如代码前缀/缓存/数据库 client）放在 packages/shared，被 ETL 与 agent 共用。
Agent（src/stock_agent / src/dev_agent）负责检索（Qdrant / MySQL）和 LLM 推理，提供 HTTP 健康与推理接口；dev_agent 包含调试/开发相关的 graph 与 UI 代码。
仪表盘（src/stock_dashboard）用于展示与交互，基于 FastAPI；notebook 下为探索性实验与演示 notebook（langchain.ipynb、4.ipynb…）。
How to run it
前置：复制并填充 .env（参见 .env.example），确保 MySQL / Redis / MinIO / Qdrant（如果使用）等凭据可用。

快速（本地 / 开发）启动示例：

bash
# 启动基础 infra（MySQL/Redis/MinIO 等）
docker-compose up -d redis mysql minio

# 启动服务容器（开发模式）
docker-compose up -d dev-agent stock-agent

# 或者用 uv 直接在本地运行（在容器外的开发方式）
uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0
stock_agent_api.sh
stock_api.sh
stock_etl_api.sh

# 启动 API server（示例）
uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 启动 langgraph 开发服务（dev_agent 需要）
cd /workspace/src/stock_agent
#（注：可能需要调整 import 路径，README 中给出本地调试提示）
uv run langgraph dev --host 0.0.0.0 --port 8002
ETL / 数据管线

必要的 env / 配置（概览）：

请参考 .env.example。常见条目包括：数据库连接（MYSQL_HOST/USER/PASSWORD/DB）、Redis、MinIO（ACCESS_KEY/SECRET_KEY）、Qdrant 地址/密钥、LLM/检索相关的 API key 或本地模型配置等。
Try asking
我想只跑 stock_etl 的某些 step（比如只跑 history），src/stock_etl/pipeline.py 支持哪些参数和断点续跑策略？（参考 stock_etl/etl_checkpoint 与 schema.sql）
src/dev_agent/langgraph.json 中定义的 graph 与 src/stock_agent 中的检索/推理如何对接？我需要如何在本地调试 langgraph 服务？
packages/shared 中有哪些模块是同时被 stock_agent 和 stock_etl 直接依赖的（例如数据库 client / 缓存装饰器 / 文本拼装工具）？在哪里可以查看使用示例？
