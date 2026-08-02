# Resume Agent / Stock Agent

一个以 **「代理 + 数据 ETL + 可视化」** 为中心的工具集合：  
把 A 股行情 / 财报 / 资讯抓取并计算因子存入 MySQL / Qdrant（`stock_etl`），提供基于检索与 LLM 推理的代理服务（`stock_agent` / `dev_agent`），并附带基于 FastAPI 的仪表盘（`stock_dashboard`）和若干实验型 Jupyter 笔记本。

目标用户：做量化因子计算、数据工程与基于检索的 Agent 原型验证的开发者与研究者。

---

## 演示

- **Demo 视频**：[Bilibili - 项目演示](https://www.bilibili.com/video/BV1Ec3X6kEnC/?vd_source=d19ada736c4a9fd9ed5f7e91130d360e)
- **架构图 (draw.io)**：[Google Drive 查看](https://drive.google.com/file/d/1uOruh8gEFiqzysdf_7AEw05jw0qGSIIY/view?usp=sharing)
- **前端 （react+typescript）**: [https://github.com/BreezySYP/stock-dashboard-ui]

示例输出（AI 投资机会深度分析报告）：

> 系统可生成类似「2026年下半年AI应用领域投资机会深度分析报告」的结构化报告，包含核心持仓池排序、多维度评分（基本面 / 技术面 / 新闻催化等）、推荐理由与风险提示。

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python、Jupyter Notebook |
| 运行时 / 框架 | uv、uvicorn、FastAPI、LangGraph |
| 数据与存储 | MySQL、Qdrant（向量检索）、Redis、MinIO |
| 监控与追踪 | Tempo、Loki、Grafana |
| 其他 | Docker / Docker Compose、devcontainer |

具体依赖请参考根目录 `pyproject.toml`、`uv.lock`、`docker-compose.yml` 以及 `.env.example`。

---

## 项目结构

```text
.devcontainer/          # 开发容器配置
.notebook/              # Jupyter 笔记本与实验脚本
Dockerfile.*            # 镜像构建文件（dev-agent / stock-agent / stock_etl）
docker-compose.yml      # 依赖服务与容器编排
entrypoint.sh           # 容器启动脚本
pyproject.toml          # 根项目依赖与工作区配置
uv.lock                 # 依赖锁文件
packages/
  shared/               # 共享包（stock_etl 与 stock_agent 共用代码）
data/                   # 数据、示例、缓存等
src/
  dev_agent/            # 开发 / 演示用 Agent（UI / graph / api）
  stock_agent/          # 代理服务：推理、检索、API 入口
  stock_dashboard/      # FastAPI 仪表盘
  stock_etl/            # 数据 ETL：sources → factors → storage
*.sh                    # 快捷启动脚本（stock_api.sh / stock_agent_api.sh / stock_etl_api.sh 等）
```
各模块如何协作

ETL（src/stock_etl）
按步骤从外部抓取行情 / 新闻 / 财报，计算因子并写入 MySQL 与 Qdrant。入口为 pipeline.py，表结构见 schema.sql。支持断点续跑。
Agent（src/stock_agent / src/dev_agent）
负责检索（Qdrant / MySQL）与 LLM 推理，提供 HTTP 健康检查与推理接口。dev_agent 包含调试用的 graph 与 UI 代码。
仪表盘（src/stock_dashboard）
基于 FastAPI，用于展示与交互。
共享代码（packages/shared）
数据库 client、缓存装饰器、文本拼装工具等被 ETL 与 Agent 共同依赖。

快速开始
1. 环境准备
Bash# 复制环境变量模板并填写
cp .env.example .env
常见配置项：

MySQL（MYSQL_HOST / USER / PASSWORD / DB）
Redis
MinIO（ACCESS_KEY / SECRET_KEY）
Qdrant 地址与密钥
LLM / 检索相关 API Key 或本地模型配置

2. 启动基础基础设施
Bashdocker-compose up -d redis mysql minio
3. 启动服务（开发模式）
Bash# 启动 Agent 相关容器
docker-compose up -d dev-agent stock-agent

# 或使用 uv 在本地直接运行
uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0

# 启动 API Server 示例
uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 启动 LangGraph 开发服务（dev_agent 需要）
cd src/stock_agent   # 或对应路径
uv run langgraph dev --host 0.0.0.0 --port 8002
也可使用项目提供的快捷脚本：
Bash./stock_agent_api.sh
./stock_api.sh
./stock_etl_api.sh
