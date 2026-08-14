# rag_memory

LLM Agent 的**分层记忆通用引擎**（uv workspace 包），与具体存储解耦。
设计参考了 Mem0（两阶段提取+更新、融合打分）、MemGPT/Letta（分层记忆）、
Generative Agents（recency×importance×relevance 检索）等主流方案。

## 为什么需要分层（短 / 中 / 长）

单层"全塞进向量库"的记忆有两个问题：相关性检索会漏掉"与问题无关但很重要"的画像/约束；
旧的会话摘要会无限堆积、污染检索。分层 + 融合打分解决这两点：

| Tier | 含义 | 典型内容 | 默认 TTL |
| --- | --- | --- | --- |
| `WORKING` | 会话内工作记忆 | 当前对话上下文 | 由上层管理，不落盘 |
| `EPISODIC` | 短期情景记忆 | 单轮/单任务摘要 | 30 天 |
| `CONSOLIDATED` | 中期整合记忆 | 多轮提炼后的结论 | 无（importance=4） |
| `SEMANTIC` | 长期语义事实 | 用户画像、偏好、约束 | 无 |
| `PROCEDURAL` | 长期程序性记忆 | 可复用分析方法、教训 | 无 |

## 模块

```text
rag_memory/
├── schemas.py    # MemoryTier / MemoryItem / MemoryQuery / MemoryWriteResult
├── store.py      # MemoryStore 协议 + InMemoryMemoryStore（测试/轻量场景）
├── engine.py     # MemoryEngine：写入判断、检索判断、consolidate 整合
├── scoring.py    # 融合打分纯函数（relevance × recency × importance）
└── extract.py    # LLM 记忆提取提示词模板
```

## 核心机制

### 写入判断（MemoryEngine.add）

1. 空内容 → `skipped`
2. `content_hash` 去重 → `deduplicated`
3. 同 namespace/tier 内语义相似度 ≥ `similar_threshold` → 新记忆写入并 `superseded` 旧记忆
   （旧记忆保留 `status=superseded` + `superseded_by`，供审计，对应 Zep 双时态思路）
4. 否则 → `created`；EPISODIC 自动补 TTL

### 检索判断（MemoryEngine.search）

```text
score = w_relevance·relevance + w_recency·recency + w_importance·importance_boost
```

- `relevance`：向量混合检索（dense + sparse）原始分，先 min-max 归一化
- `recency`：指数衰减（半衰期可配，默认 14 天，下限 0.2）
- `importance`：1-5 映射到 [0, 0.5] 增量
- 可选 `recall_important_top_k`：与 query 无关但高重要性的记忆兜底注入
  （MemGPT/Generative Agents 思路，保证"用户只看成长股"这类约束不会被漏掉）

### 整合（MemoryEngine.consolidate）

把近期 `EPISODIC` 记忆交给 `summarizer`（LLM 回调），产出 `CONSOLIDATED` 中期记忆，
并在 `metadata.source_ids` 记录来源，避免信息丢失。

## 使用

```python
from rag_memory.engine import MemoryEngine
from rag_memory.schemas import MemoryItem, MemoryQuery, MemoryTier
from rag_memory.store import InMemoryMemoryStore

engine = MemoryEngine(InMemoryMemoryStore(), similar_threshold=0.88)

engine.add(MemoryItem(
    user_id="u1", namespace="user:u1:profile", tier=MemoryTier.SEMANTIC,
    content="用户只看成长股", importance=5,
))

items = engine.search(MemoryQuery(user_id="u1", query="技术面怎么看", limit=5),
                      recall_important_top_k=1)
```

生产环境请实现 `MemoryStore` 协议（如 `stock_agent/memory/store.py` 的
`StockMemoryStore`：Qdrant 混合检索 + MySQL 元数据），协议方法见 `store.py`。

## 测试

```bash
uv run pytest tests/rag_memory
```

覆盖：打分单调性/边界、去重、相似替换、TTL、tier 过滤、重要记忆兜底、整合、提示词模板、
存储状态机等。**当前 `--cov=rag_memory` 为 100%**，CI 有 `--cov-fail-under=95` 门槛防回退。
