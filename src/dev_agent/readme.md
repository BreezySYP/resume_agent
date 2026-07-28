What this is
一个以 Python 为主的多模块仓库，围绕股票相关的 Agent、数据 ETL 与可视化仪表盘构建：dev_agent 提供 LangGraph 驱动的多角色推理流程（带 UI 与 Supervisor/Generalist/Capitalist 节点），stock_etl 负责行情/财报/资讯的抓取与因子计算并写入 MySQL/Qdrant，为 stock_agent 的检索与推理提供数据支持，stock_dashboard/streamlit 提供展示层。适用于做股票数据采集、因子计算与基于检索的 LLM 问答/Agent 原型的开发者或研究者。

Stack
Language(s): Python (主要)
Framework / runtime: LangGraph + LangChain 风格的 agent 流程；Streamlit 用于 UI；uvicorn 用于 HTTP/ASGI 服务；常见容器化（Docker / docker-compose）
Notable libraries: langgraph / langchain_core / langsmith（Agent/Graph）、streamlit（UI）、qdrant-client（向量存储，stock_etl 同步）、redis（checkpoint / 缓存）
How it's organized
Code
README.md
pyproject.toml                 # 仓库级依赖/metadata
docker-compose.yml
Dockerfile.dev-agent
Dockerfile.stock-agent
Dockerfile.stock_etl
data/                          # 示例数据 / 资源（简历等）
notebook/                      # Jupyter notebooks
packages/                      # monorepo shared packages
  shared/                      # 共享工具：MySQL pool, Qdrant client, Redis 装饰器等
src/
  dev_agent/                   # LangGraph agent + UI + workflow (Supervisor/Capitalist/Generalist/Reflection/Final_Answer)
    api/server.py              # 启动/演示入口（构建 graph 并 invoke）
    graph/
      workflow.py              # StateGraph 组装：Supervisor/Capitalist/Generalist/Reflection/Final_Answer
      nodes.py                 # 各节点实现（Capitalist 调用 stock_agent 的 RemoteGraph）
    ui/                        # streamlit UI
    rag/                       # RAG helper / ingestion
    pyproject.toml             # dev_agent 子包依赖
  stock_agent/                 # Agent 服务（处理金融问题、对外暴露 remote graph）
  stock_etl/                   # 股票数据 ETL（sources -> factors -> storage; 同步到 MySQL/Qdrant）
    README.md                  # ETL 用法、pipeline 入口和断点续跑说明
  stock_dashboard/             # 仪表盘/展示（Streamlit 或其它前端）
docker-compose.yml             # 启动依赖：redis / mysql / minio + services
.env.example                   # 环境变量样例
entrypoint.sh
loki-config.yaml, tempo.yaml   # 可观察性 / tracing 配置
How it fits together:

数据生产线：stock_etl 定时/按需抓取行情、新闻与财报，计算因子并写入 MySQL，同时可把部分文本/画像同步到 Qdrant，形成可检索的上下文。
推理层：stock_agent 提供可被远程调用的 Graph 节点（在 dev_agent 的 capitalist_node 中通过 RemoteGraph 调用），负责领域（股票）问题的检索与推理。
协调与 UI：dev_agent 用 LangGraph 组装多角色工作流（Supervisor 决策路由到 Capitalist/Generalist/Final_Answer），并可以通过 streamlit 提供交互界面；最终答案阶段会异步触发 RAGAS 评估。
运行时通过 docker-compose 启动基础设施（redis/mysql/minio），并用各自的 Dockerfile/uvicorn/streamlit 启动服务。
How to run it
最短路径（本地机器 / 开发环境）——摘自 README 中的常用命令：

启动基础设施（redis / mysql / minio）和两个服务
bash
docker-compose up -d redis mysql minio
docker-compose up -d dev-agent stock-agent
检查健康（示例端口）
bash
curl http://localhost:8003/health   # dev-agent 健康检查（示例）
curl http://localhost:8004/health   # stock-agent 健康检查（示例）
在容器内相互访问测试（在 dev-agent 容器里）
bash
docker exec -it <dev-agent容器> curl http://stock-agent:8004/health
本地开发运行 UI / 服务（非容器）
bash
# Streamlit UI
uv run streamlit run src/main.py \
  --server.port=8501 --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false

# LangGraph 本地调试（dev_agent）
uv run langgraph dev --host 0.0.0.0 --port 8002

# 启动 ASGI 服务示例
uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload

注意/所需环境变量

仓库含 .env.example，需要配置（典型项）：REDIS_URL、STOCK_AGENT_URL、MySQL 连接字符串、QDRANT 配置、MinIO creds 等。dev_agent 的 nodes.py 显式使用 REDIS_URL 与 STOCK_AGENT_URL（或默认 localhost:8002）。
