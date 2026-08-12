import asyncio
import json
from typing import List, Dict, Set

from loguru import logger

from shared.models.deepseek import get_deepseek
from shared.metrics.prome import ainvoke_with_metrics

_BATCH_LLM = 50
_SCOPE_MAX_LENGTH = 100
_MAX_CONCURRENCY = 5  # 最多 5 路并发


model_name = "deepseek-chat"
model = get_deepseek(model=model_name)


def _build_prompt(query: str, candidates: List[Dict]) -> str:
    candidates_text = "\n".join([
        f"{s['code']} {s['name']} - {s.get('business', '')[:_SCOPE_MAX_LENGTH]}"
        for s in candidates
    ])
    return f"""
        用户问题："{query}"

        请从以下候选股票中选出**业务上真正相关**的股票。

        候选股票：
        {candidates_text}

        判断标准：
        - 该股票的业务与用户问题直接相关
        - 只需要判断"是否相关"，不需要考虑估值、股价等

        返回JSON数组（只返回代码）：
        ["000977", "002230", ...]
        """


async def _select_one_batch(
    query: str,
    batch: List[Dict],
    sem: asyncio.Semaphore,
) -> List[str]:
    async with sem:
        try:
            logger.debug("debug _select_one_batch")
            prompt = _build_prompt(query, batch)
            response = await ainvoke_with_metrics(model, prompt, "golden_standard", model_name)
            return json.loads(response.content)
        except Exception as e:
            # 单批失败不拖垮整体，按需改成 raise
            logger.error(f"[golden] batch failed: {e}")
            return []


async def get_golden_standard(
    query: str,
    candidates: list,
    llm_batch_size: int = _BATCH_LLM,
    max_concurrency: int = _MAX_CONCURRENCY,
    refresh: bool = False,
) -> Set[str]:
    """
    异步获取黄金标准，最多 max_concurrency 路并发调用 LLM。
    """
    if not candidates:
        return set()

    batches = [
        candidates[i:i + llm_batch_size]
        for i in range(0, len(candidates), llm_batch_size)
    ]

    sem = asyncio.Semaphore(max_concurrency)
    tasks = [_select_one_batch(query, batch, sem) for batch in batches]
    results = await asyncio.gather(*tasks)

    all_selected: Set[str] = set()
    for selected in results:
        all_selected.update(selected)
    return all_selected


if __name__ == "__main__":
    from agent.tools import search_stock_profile

    query = "AI应用相关的股票信息"
    candidates = search_stock_profile.invoke({"query": query})
    codes = asyncio.run( get_golden_standard(query, candidates))
    
    print(codes)


