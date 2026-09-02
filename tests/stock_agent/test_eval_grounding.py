"""faithfulness 主流程与 eval 早退判断的单测（不依赖外部服务）。"""
import asyncio

import agent.nodes.eval_node as en
import numpy as np
from eval import faithfulness


def test_has_grounding_evidence():
    assert en._has_grounding_evidence({}) is False
    assert en._has_grounding_evidence({"news_items": [], "stock_profile": []}) is False
    assert en._has_grounding_evidence({"memory_context": "x"}) is True
    assert en._has_grounding_evidence({"stock_profile": [{}]}) is True
    assert en._has_grounding_evidence({"news_items": ["新闻"]}) is True


def test_assemble_rag_returns_sentences_from_all_fields():
    rag_context = [
        {
            "source": "profile",
            "code": "600001",
            "name": "公司600001",
            "business": "工业软件",
            "scope": "",
            "update_time": "2026-01-01 00:00:00",
        },
        {"source": "technical", "code": "600001", "trend_score": 0.81},
        {"source": "financial", "code": "600001", "profitability_score": 0.72},
        {
            "source": "news",
            "id": 1,
            "code": "600001",
            "name": "公司600001",
            "date": "2026-01-01 00:00:00",
            "title": "发布中报",
            "content": "净利增长。",
            "mediaName": "媒体",
            "url": "http://example.com",
        },
        {"source": "memory", "memory": "用户偏好稳健"},
    ]
    sentences = faithfulness.assemble_rag(rag_context)
    assert isinstance(sentences, list)
    assert len(sentences) == len(rag_context)
    assert all(isinstance(s, str) and s for s in sentences)
    assert any("600001" in s for s in sentences)


def test_claims_prompt_requires_stock_code():
    prompt = faithfulness._build_claims_prompt("答案", "问题", 10)
    assert "股票代码" in prompt
    assert "6位" in prompt
    assert "603859" in prompt


def test_extract_claims_caps_count(monkeypatch):
    async def fake_chat(prompt):
        return "\n".join(f"{i}. 第{i}条声明。" for i in range(1, 15))

    monkeypatch.setattr(faithfulness, "_chat", fake_chat)
    claims = asyncio.run(faithfulness._extract_claims("答案", "问题", 5))
    assert len(claims) == 5
    assert claims[0] == "第1条声明。"
    assert claims[-1] == "第5条声明。"


def test_claim_ok_selects_top_k_evidence(monkeypatch):
    async def fake_support(claim, evidence):
        return 1.0

    monkeypatch.setattr(faithfulness, "_claim_support", fake_support)

    sentences = ["证据一。", "证据二。", "证据三。"]
    score = np.array([0.9, 0.8, 0.1])

    async def run():
        sem = asyncio.Semaphore(1)
        return await faithfulness._claim_ok(
            "陈述一。",
            score,
            sem,
            sentences,
            top_k=5,
        )

    result = asyncio.run(run())
    assert result["supported"] == 1.0
    # 取 top-k，且低于阈值 0.25 的句子被排除
    assert result["evidence"] == ["证据一。", "证据二。"]
    assert result["claim"] == "陈述一。"


def test_claim_ok_caps_evidence_by_top_k(monkeypatch):
    async def fake_support(claim, evidence):
        return 1.0

    monkeypatch.setattr(faithfulness, "_claim_support", fake_support)

    sentences = ["证据一。", "证据二。", "证据三。", "证据四。"]
    score = np.array([0.9, 0.8, 0.7, 0.6])

    async def run():
        sem = asyncio.Semaphore(1)
        return await faithfulness._claim_ok(
            "陈述一。",
            score,
            sem,
            sentences,
            top_k=2,
        )

    result = asyncio.run(run())
    assert result["supported"] == 1.0
    assert result["evidence"] == ["证据一。", "证据二。"]
