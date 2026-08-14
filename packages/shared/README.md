# shared

跨服务共用库（uv workspace 包），被 `dev_agent` / `stock_agent` / `stock_etl` / `stock_dashboard` 共同依赖。
这里是全仓库唯一持有基础设施连接、统一配置与通用能力的地方。

## 模块

| 模块 | 说明 |
| --- | --- |
| `configs/` | 统一配置 `settings.py`（pydantic-settings，读取 `.env`）+ 日志 `log_config.py` |
| `db/` | MySQL 连接池、Redis 缓存 / 队列 / SSE、Qdrant client |
| `models/` | Ollama / DeepSeek / Groq LLM 与 Embedding 单例、稀疏向量 |
| `rag/` | RAG 检索相关（向量存储、评估工具） |
| `safety/` | 输入输出 guardrails、限流器 |
| `text/` | 股票文本拼装（新闻 / 简介 / payload 构建） |
| `web/` | `create_app()` 统一 FastAPI 工厂（日志 / CORS / 健康检查 / `/metrics`） |
| `metrics/` | Prometheus 指标封装 |
| `agents/` | LangGraph AgentState 与 checkpointer 封装 |

## 使用

在某个成员包的 `pyproject.toml` 中声明依赖即可：

```toml
[tool.uv.sources]
shared = { workspace = true }
```

```python
from shared.configs.settings import OLLAMA_URL, REDIS_URL
from shared.web.app import create_app
from shared.db.mysql import engine
```

## 配置

所有服务共享同一套环境变量配置，模板见仓库根目录 `.env.example`：

- 优先级：真实环境变量 > `.env` > 代码默认值（容器部署通过 `environment` / `env_file` 注入）。
- `.env` 中的所有键会注入 `os.environ`，`os.getenv` 消费者（Tavily / LangSmith / OTel 等）可直接读取。

## 测试

测试位于仓库根目录 `tests/shared/`，与 `shared.*` 模块一一对应。
