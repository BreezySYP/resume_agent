"""rag_memory — LLM Agent 分层记忆通用引擎。

提供与具体存储（Qdrant / MySQL / Redis）无关的核心能力：

- `MemoryTier`：working / episodic(短) / consolidated(中) / semantic(长) / procedural(长)
- `MemoryStore`：存储协议 + `InMemoryMemoryStore`（测试/轻量场景）
- `MemoryEngine`：写入判断（去重 / 相似替换 / 过期）、检索判断（融合打分 + 重要记忆兜底）、定期整合
- `scoring`：relevance × recency × importance 融合打分（纯函数）
- `extract`：LLM 记忆提取提示词模板
"""

from rag_memory.engine import MemoryEngine
from rag_memory.schemas import (
    MemoryCandidate,
    MemoryItem,
    MemoryQuery,
    MemoryStatus,
    MemoryTier,
    MemoryWriteResult,
)
from rag_memory.scoring import fusion_score, importance_boost, recency_weight
from rag_memory.store import InMemoryMemoryStore, MemoryStore

__all__ = [
    "MemoryEngine",
    "MemoryCandidate",
    "MemoryItem",
    "MemoryQuery",
    "MemoryStatus",
    "MemoryTier",
    "MemoryWriteResult",
    "InMemoryMemoryStore",
    "MemoryStore",
    "fusion_score",
    "importance_boost",
    "recency_weight",
]
