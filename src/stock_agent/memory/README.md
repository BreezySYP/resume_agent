# stock_agent/memory

`stock_agent` 的**记忆领域适配层**。通用算法（分层、融合打分、写入判断、整合）在
`packages/rag_memory`，本模块只负责：领域模型（`MemoryType`/`MemoryRecord` 等）、
Qdrant + MySQL 存储适配、与 LangGraph 节点的对接。

## 架构

```text
memory_recall_node ──search_for_prompt──▶ MemoryService ──▶ MemoryEngine(rag_memory)
memory_write_node  ──add_from_extract──▶      │                    │
                                              ▼                    ▼
                                       StockMemoryStore     Qdrant(hybrid) + MySQL
```

- `models.py`：`MemoryType` / `MemoryStatus` / `MemorySource` / DTO，以及
  `MemoryType → MemoryTier` 映射
- `dto.py`：row → `MemoryRecord`、`MemoryRecord` ⇄ `MemoryItem` 双向往返、prompt 文本拼装
- `store.py`：`StockMemoryStore` 实现 `rag_memory.MemoryStore`
  （Qdrant 混合检索 + MySQL 元数据/状态）
- `mysql_repo.py`：MySQL 仓储（惰性加载 engine，import 不连库）
- `mem_service.py`：`MemoryService` 领域门面，保持旧公共 API

## 分层映射

| MemoryType | rag_memory Tier | 说明 |
| --- | --- | --- |
| `profile` | `semantic`（长） | 用户画像、偏好、约束 |
| `episode` | `episodic`（短，默认 30 天 TTL） | 单轮会话/任务摘要 |
| `summary` | `consolidated`（中） | 多轮整合后的结论 |
| `procedural` / `lesson` | `procedural`（长） | 可复用分析方法、教训 |

## 关键流程

### 写入（memory_write_node）

1. LLM 用 `rag_memory.extract.build_extract_prompt` 提取 `MemoryExtractResult`
2. `MemoryService.add_from_extract_batch` → `MemoryEngine.add`：
   去重（content hash）→ 语义相似替换（≥ `similar_threshold`，旧记忆保留为 `superseded`）
   → 写入 MySQL + Qdrant

### 检索（memory_recall_node）

`MemoryService.search_for_prompt` → `MemoryEngine.search`：

```text
score = 0.6·relevance + 0.25·recency + 0.15·importance_boost
```

并默认 `recall_important_top_k=1`：把与问题无关但高重要性的记忆（如用户约束）兜底注入
supervisor 上下文，防止画像类记忆因"本次检索不到"而丢失。

### 整合（中期记忆）

`MemoryService.consolidate(user_id, summarizer=...)` 把近期 `episode` 交给 LLM
摘要，产出 `summary` 类型（`consolidated` tier）记忆。当前节点未默认触发，可按需
在每日/每周任务中调用：

```python
svc.consolidate("u1", summarizer=lambda records: summarize_with_llm(records))
```

## 配置项（MemoryService）

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `similar_threshold` | 0.88 | 相似替换阈值 |
| `use_hybrid` | True | Qdrant dense+sparse 混合检索 |
| `default_episode_days` | 30 | episode 默认 TTL |
| `recall_important_top_k` | 1 | 高重要性记忆兜底注入条数 |

## 存储

- Qdrant collection：`agent_memories`（dense + sparse 混合，payload 含
  `user_id` / `namespace` / `memory_type` / `tier` / `status` / `importance`）
- MySQL 表：`agent_memories`（元数据 + 状态机 `active/superseded/conflict/deleted`，
  建表见 `schema.sql`）

## 测试

- `tests/rag_memory/`：引擎与打分（纯内存，无外部依赖）
- `tests/stock_agent/test_memory_service.py`：领域门面（注入 `InMemoryMemoryStore`）
- `tests/stock_agent/test_memory_dto.py`：DTO 转换
