"""profile_node 单测：单轮并行检索 + 池级精排降级（monkeypatch 检索/rerank/LLM，不依赖外部服务）。"""
from types import SimpleNamespace

import agent.nodes.profile_node as pn
import pandas as pd
import pytest


def _profile(code: int, **overrides) -> dict:
    data = {
        "code": str(code),
        "name": f"公司{code}",
        "business": f"主营业务{code}",
        "scope": f"业务详情{code}",
        "update_time": "2026-08-27 10:00:00",
        "original_score": float(code % 10) / 10,
        "rerank_score": 0.0,
    }
    data.update(overrides)
    return data


def _fake_llm(content: str, *, fail: bool = False):
    def _invoke(model, prompt, source, model_name):
        if fail:
            raise RuntimeError("llm down")
        return SimpleNamespace(content=content)

    return _invoke


def _noop_rerank(query, docs) -> pd.DataFrame:
    scores = [float(len(docs) - i) for i in range(len(docs))]
    return pd.DataFrame({"rerank_score": scores, "docs": docs})


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    """节点装饰器会向 Redis 推送事件，测试里置为 no-op。"""
    monkeypatch.setattr("event.event_manager.push_queue", lambda *a, **k: None)


@pytest.fixture()
def _patch_llm(monkeypatch):
    monkeypatch.setattr(
        pn,
        "get_deepseek",
        lambda model="deepseek-chat", temperature=0.0: SimpleNamespace(),
    )


def test_single_round_parallel_search_dedup_top10(monkeypatch, _patch_llm):
    calls = []

    def _invoke(model, prompt, source, model_name):
        calls.append(1)
        return SimpleNamespace(content='{"keywords": ["芯片", "半导体", "机器人"]}')

    monkeypatch.setattr(pn, "invoke_with_metrics", _invoke)

    searched = {}

    def _search(args):
        query = args["query"]
        searched[query] = searched.get(query, 0) + 1
        mapping = {
            "芯片": [_profile(600001), _profile(600002), _profile(600003), _profile(600004)],
            "半导体": [_profile(600003), _profile(600005), _profile(600006), _profile(600007)],
            "机器人": [_profile(600008), _profile(600009), _profile(600010), _profile(600011)],
        }
        return mapping.get(query, [])

    monkeypatch.setattr(pn, "search_stock_profile", SimpleNamespace(invoke=_search))
    monkeypatch.setattr(pn, "rerank", _noop_rerank)

    result = pn.profile_node(
        {"user_question": "AI 芯片投资机会", "job_id": "j1", "thread_id": "t1"}
    )

    assert len(calls) == 1  # 关键词只生成一次
    assert set(searched) == {"芯片", "半导体", "机器人"}  # 所有关键词都被检索
    records = result["stock_profile"]
    assert len(records) == 10  # 去重后 11 只，rerank 取 top-10
    assert [r["code"] for r in records] == [str(c) for c in range(600001, 600011)]


def test_rerank_failure_falls_back_to_original_score(monkeypatch, _patch_llm):
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm('{"keywords": ["芯片"]}'))

    def _search(args):
        return [_profile(c) for c in range(600001, 600013)]

    monkeypatch.setattr(pn, "search_stock_profile", SimpleNamespace(invoke=_search))

    def _rerank_down(query, docs):
        raise RuntimeError("rerank down")

    monkeypatch.setattr(pn, "rerank", _rerank_down)

    result = pn.profile_node({"user_question": "q", "job_id": "j", "thread_id": "t"})
    records = result["stock_profile"]
    assert len(records) == 10
    assert records[0]["code"] == "600009"  # original_score = code%10/10 最大者排第一
    assert all("scope" not in r for r in records)


def test_keyword_extraction_failure_falls_back_to_question(monkeypatch, _patch_llm):
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm("", fail=True))
    searched = []

    def _search(args):
        query = args["query"]
        searched.append(query)
        return [_profile(600001)]

    monkeypatch.setattr(pn, "search_stock_profile", SimpleNamespace(invoke=_search))
    monkeypatch.setattr(pn, "rerank", _noop_rerank)

    result = pn.profile_node({"user_question": "电力板块", "job_id": "j", "thread_id": "t"})
    assert searched == ["电力板块"]
    assert [r["code"] for r in result["stock_profile"]] == ["600001"]


def test_single_search_failure_is_skipped(monkeypatch, _patch_llm):
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm('{"keywords": ["好", "坏"]}'))

    def _search(args):
        query = args["query"]
        if query == "坏":
            raise RuntimeError("search down")
        return [_profile(600001)]

    monkeypatch.setattr(pn, "search_stock_profile", SimpleNamespace(invoke=_search))
    monkeypatch.setattr(pn, "rerank", _noop_rerank)

    result = pn.profile_node({"user_question": "q", "job_id": "j", "thread_id": "t"})
    assert [r["code"] for r in result["stock_profile"]] == ["600001"]


def test_empty_results_return_empty(monkeypatch, _patch_llm):
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm('{"keywords": ["无结果"]}'))
    monkeypatch.setattr(
        pn,
        "search_stock_profile",
        SimpleNamespace(invoke=lambda args: []),
    )
    monkeypatch.setattr(pn, "rerank", _noop_rerank)

    result = pn.profile_node({"user_question": "q", "job_id": "j", "thread_id": "t"})
    assert result == {"stock_profile": []}


def test_rerank_text_uses_build_stock_profile_text_with_scope_fallback(monkeypatch):
    captured = {}

    def _fake_rerank(query, docs):
        captured["docs"] = docs
        return pd.DataFrame({"rerank_score": [1.0] * len(docs), "docs": docs})

    monkeypatch.setattr(pn, "rerank", _fake_rerank)

    # scope 为空字符串：兜底用 business，文本与 build_stock_profile_text 一致
    df_with_empty_scope = pd.DataFrame([_profile(600001, scope="")])
    pn._rank(df_with_empty_scope, "q")
    expected = pn.build_stock_profile_text(
        {
            "name": "公司600001",
            "code": "600001",
            "business": "主营业务600001",
            "scope": "主营业务600001",
            "update_time": "2026-08-27 10:00:00",
        }
    )
    assert captured["docs"][0] == expected

    # scope 列完全缺失：同样兜底，不抛 KeyError
    row = _profile(600002)
    row.pop("scope")
    df_without_scope = pd.DataFrame([row])
    pn._rank(df_without_scope, "q")
    expected_without_scope = pn.build_stock_profile_text(
        {
            "name": "公司600002",
            "code": "600002",
            "business": "主营业务600002",
            "scope": "主营业务600002",
            "update_time": "2026-08-27 10:00:00",
        }
    )
    assert captured["docs"][-1] == expected_without_scope


def _run_profile_flow(monkeypatch, review_result):
    """跑通 profile_node 主流程：关键词→检索→rerank→审核，返回 stock_profile。"""
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm('{"keywords": ["芯片"]}'))

    def _search(args):
        return [_profile(c) for c in range(600001, 600013)]

    monkeypatch.setattr(pn, "search_stock_profile", SimpleNamespace(invoke=_search))
    monkeypatch.setattr(pn, "rerank", _noop_rerank)
    monkeypatch.setattr(pn, "_review_profiles", lambda question, candidates: review_result)
    return pn.profile_node({"user_question": "q", "job_id": "j", "thread_id": "t"})[
        "stock_profile"
    ]


def test_review_keeps_only_named_codes(monkeypatch, _patch_llm):
    records = _run_profile_flow(monkeypatch, ["600005"])
    assert [r["code"] for r in records] == ["600005"]


def test_review_empty_returns_top10(monkeypatch, _patch_llm):
    records = _run_profile_flow(monkeypatch, [])
    assert [r["code"] for r in records] == [str(c) for c in range(600001, 600011)]


def test_review_codes_not_in_pool_falls_back_top10(monkeypatch, _patch_llm):
    records = _run_profile_flow(monkeypatch, ["999999"])
    assert [r["code"] for r in records] == [str(c) for c in range(600001, 600011)]


def test_review_profiles_returns_keep_codes(monkeypatch):
    monkeypatch.setattr(
        pn,
        "get_deepseek",
        lambda model="deepseek-chat", temperature=0.0: SimpleNamespace(
            with_structured_output=lambda schema: "structured-chain"
        ),
    )
    monkeypatch.setattr(
        pn,
        "invoke_with_metrics",
        lambda model, prompt, source, model_name: SimpleNamespace(keep_codes=["600001"]),
    )
    assert pn._review_profiles("兆易创新怎么样？", [{"code": "600001", "name": "兆易创新"}]) == [
        "600001"
    ]


def test_review_profiles_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(pn, "invoke_with_metrics", _fake_llm("", fail=True))
    assert pn._review_profiles("q", [{"code": "600001", "name": "公司600001"}]) == []
    assert pn._review_profiles("q", []) == []
