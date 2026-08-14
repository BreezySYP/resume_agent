# stock_agent

A 股智能投研 Agent：基于 LangGraph 的多节点分析流程，通过 SSE 实时推送回答进度。

## 架构

LangGraph 主流程（`agent/graph.py`）：

```text
memory_recall → supervisor → profile → fundamental / technical / news（并行）
              → synthesizer → reflection ⇄ synthesizer → memory_write → eval
```

- `agent/nodes/`：各分析节点实现；`agent/routing.py`：reflection 后的条件路由；`agent/tools.py`：工具与外部调用。
- `memory/`：长期记忆（MySQL 元数据 + Qdrant 混合检索，`mem_service.py` 编排）。
- `service/`：Qdrant 检索（`qdrant_search.py`）、业务相似检索与重排（`search_similar.py` + `cuda_service.py`）、
  SQL 工具（`sql_helper.py`）。
- `eval/`：faithfulness / feedback / golden_standard 评估。
- `observe/metrics.py`：Prometheus 指标（`/metrics`）。
- `core/minio_file.py`：MinIO 文件管理。

## 运行

```bash
cd src/stock_agent

# API 服务
uv run uvicorn main:app --host 0.0.0.0 --port 8004

# LangGraph Studio（Docker 镜像使用这种方式）
uv run langgraph dev --host 0.0.0.0 --port 8004
```

Swagger 文档：<http://localhost:8004/docs>

## API

### 触发 Agent 回答

```bash
curl -X POST http://localhost:8004/api/ai/qa \
  -H 'Content-Type: application/json' \
  -d '{"thread_id": "demo", "job_id": "job-1", "question": "贵州茅台近一年走势如何？"}'
```

### 订阅回答进度（SSE）

```bash
curl -N http://localhost:8004/api/ai/qa/stream/job-1
```

## 依赖

- Redis（checkpoint / SSE 队列）、MySQL（元数据）、Qdrant（向量检索）、MinIO（文件）、Ollama（LLM / Embedding）
- 配置统一读取仓库根 `.env`，见 `.env.example` 模板
