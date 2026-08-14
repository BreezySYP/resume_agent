# dev_agent

多 Agent 编码助手：RAG 知识库 + Supervisor 多 Agent 协作，支持本地文档入库与 RAGAS 评估。

## 架构

- `graph/workflow.py`：LangGraph StateGraph 组装，节点为 Supervisor / Capitalist / Generalist /
  Reflection / Final_Answer，checkpointer 使用 Redis。
- `rag/`：本地文件入库（`ingest.py`，支持 pdf / txt / md）、向量库读写（`vector_store.py`）、检索工具（`tools.py`）。
- `ragas_eval/`：基于 RAGAS 的检索 / 生成质量评估。
- `ui/streamlit_app.py`：Streamlit 前端。
- `api/server.py`：LangGraph 服务入口（`langgraph.json` 指向 `./api/server.py:graph`）。

## 运行

### LangGraph API / Studio

```bash
cd src/dev_agent
uv run langgraph dev --host 0.0.0.0 --port 8003
```

### Streamlit UI

```bash
cd src/dev_agent
uv run streamlit run api/server.py --server.port=8501 --server.address=0.0.0.0
```

### 本地文档入库（RAG）

```bash
cd src/dev_agent
uv run python -m rag.ingest docs/resume.pdf docs/jd.md
```

## 依赖

- Redis（checkpoint / 向量缓存）、Ollama（LLM / Embedding）、Qdrant（可选向量库）
- 需要 `shared` workspace 包；配置统一读取仓库根 `.env`
