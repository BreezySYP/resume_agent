"""shared.db.qdrant_writer 文本预处理测试（embedding 前截断超长文本）。"""
import pandas as pd
import pytest
from shared.db.qdrant_writer import (
    MAX_EMBED_TEXT_CHARS,
    _chunk_text,
    _embed_with_adaptive_truncation,
    _embed_with_retry,
    _fit_embed_texts,
    _prepare_batch,
)
from shared.text.stock_text import build_stock_news_text, get_stock_news_payload


def test_fit_embed_texts_keeps_short_texts():
    texts = ["短文本", "another short text", "中文内容" * 100]
    fitted = _fit_embed_texts(texts)
    assert fitted == texts


def test_fit_embed_texts_truncates_long_text():
    long_text = "长" * (MAX_EMBED_TEXT_CHARS + 100)
    fitted = _fit_embed_texts([long_text])[0]
    assert len(fitted) == MAX_EMBED_TEXT_CHARS
    assert fitted.startswith("长" * 100)


def test_fit_embed_texts_preserves_head():
    long_text = "标题" + "正文" * (MAX_EMBED_TEXT_CHARS + 1)
    fitted = _fit_embed_texts([long_text])[0]
    assert fitted.startswith("标题")


class FakeEmbeddingModel:
    """模拟 Ollama：超过 limit 字符的输入抛 context 超长错误。"""

    def __init__(self, limit: int, error: str = "the input length exceeds the context length (status code: 400)"):
        self.limit = limit
        self.error = error
        self.calls: list[list[int]] = []

    def __call__(self, texts):
        self.calls.append([len(t) for t in texts])
        for t in texts:
            if len(t) > self.limit:
                raise RuntimeError(self.error)
        return [[float(i)] for i in range(len(texts))]


def test_embed_adaptive_truncation_only_cuts_offending_text():
    # 模拟真实案例：文本 5288 字符，但服务端只接受前 2917 字符
    long_text = "长文" * 2644  # 5288 字符
    short_text = "正常短文本"
    model = FakeEmbeddingModel(limit=2917)

    vectors = _embed_with_adaptive_truncation(model, [long_text, short_text])

    assert len(vectors) == 2
    # 短文本原样嵌入，长文本最终用 ≤2917 字符的片段
    assert [1500] in model.calls
    assert [len(short_text)] in model.calls


def test_embed_with_retry_falls_back_on_context_error():
    model = FakeEmbeddingModel(limit=1500)

    vectors = _embed_with_retry(model, ["a" * 5000, "short"], retries=3, backoff=0)

    assert len(vectors) == 2
    # 短文本按原样嵌入，超长文本截断后成功
    assert [1500] in model.calls
    assert [len("short")] in model.calls


def test_embed_with_retry_retries_transient_errors_then_raises():
    class FlakyModel:
        def __init__(self):
            self.calls = 0

        def __call__(self, texts):
            self.calls += 1
            raise RuntimeError("connection reset")

    model = FlakyModel()
    with pytest.raises(RuntimeError, match="connection reset"):
        _embed_with_retry(model, ["x"], retries=3, backoff=0)
    assert model.calls == 3


def test_chunk_text_short_returns_as_is():
    assert _chunk_text("短文", 2000, 200) == ["短文"]
    assert _chunk_text("", 2000, 200) == [""]


def test_chunk_text_all_chunks_within_size():
    text = "段" * 10000
    chunks = _chunk_text(text, 2000, 200)
    assert [len(c) for c in chunks] == [2000, 2000, 2000, 2000, 2000, 1000]


def test_chunk_text_overlap():
    # 用可区分内容：没有 overlap 时窗口是 [0:2000],[2000:4000],[4000:5000]，
    # 只有真正重叠才会得到 [1800:3800] 这种窗口
    text = "".join(str(i % 10) for i in range(5000))
    chunks = _chunk_text(text, 2000, 200)
    assert chunks == [text[0:2000], text[1800:3800], text[3600:5000]]
    assert chunks[1][:200] == chunks[0][-200:] == text[1800:2000]


def test_chunk_text_prefers_newline_boundary():
    text = "a" * 1800 + "\n" + "b" * 5000
    chunks = _chunk_text(text, 2000, 200)
    assert chunks[0] == "a" * 1800 + "\n"


def test_prepare_batch_non_chunked_preserves_behavior():
    df = pd.DataFrame([{
        "id": 123, "name": "n", "code": "c", "title": "t",
        "date": "2026-01-01", "content": "内容", "mediaName": "m", "url": "u",
    }])
    texts, point_ids, payloads, stale_ids, article_ids = _prepare_batch(
        df, build_stock_news_text, get_stock_news_payload
    )
    assert point_ids == [123]
    assert payloads == [get_stock_news_payload(df.iloc[0])]
    assert stale_ids == [] and article_ids == []


def test_prepare_batch_chunked_splits_into_multiple_points():
    df = pd.DataFrame([{
        "id": 7, "name": "n", "code": "c", "title": "t",
        "date": "2026-01-01", "content": "内" * 5000, "mediaName": "m", "url": "u",
    }])
    texts, point_ids, payloads, stale_ids, article_ids = _prepare_batch(
        df, build_stock_news_text, get_stock_news_payload, chunk_size=2000, chunk_overlap=200
    )
    full = build_stock_news_text(df.iloc[0])
    # 全文 5090 字符，切 2000/重叠 200 → 精确窗口
    assert len(full) == 5090
    assert texts == [full[0:2000], full[1800:3800], full[3600:len(full)]]
    assert len(texts) == 3
    assert [len(t) for t in texts] == [2000, 2000, 1490]
    assert len(point_ids) == len(payloads) == 3
    assert stale_ids == [7]
    assert article_ids == ["7"]
    assert [p["article_id"] for p in payloads] == ["7", "7", "7"]
    assert [p["chunk_index"] for p in payloads] == [0, 1, 2]
    assert len(set(point_ids)) == len(point_ids)
