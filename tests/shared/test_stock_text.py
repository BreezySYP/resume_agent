"""shared.text.stock_text 文本/payload 构造测试。"""
from shared.text.stock_text import (
    build_business_breakdown_text,
    build_stock_news_text,
    build_stock_profile_text,
    get_business_breakdown_payload,
    get_stock_news_payload,
    get_stock_profile_payload,
)


def test_news_text_contains_fields():
    row = {
        "name": "贵州茅台",
        "code": "600519",
        "date": "2026-01-01",
        "title": "年报预增",
        "content": "内容",
        "mediaName": "东方财富",
        "url": "http://x",
    }
    text = build_stock_news_text(row)
    for field in ("贵州茅台", "600519", "2026-01-01", "年报预增", "内容", "东方财富", "http://x"):
        assert field in text


def test_news_payload_str_date():
    row = {
        "name": "n", "code": "c", "title": "t", "date": "2026-01-01",
        "mediaName": "m", "url": "u",
    }
    assert get_stock_news_payload(row) == {
        "code": "c", "name": "n", "title": "t",
        "date": "2026-01-01", "media": "m", "url": "u",
    }


def test_profile_text_and_payload():
    row = {"name": "n", "code": "c", "business": "b", "scope": "s", "update_time": "2026-01-01"}
    text = build_stock_profile_text(row)
    assert "b" in text and "s" in text
    assert get_stock_profile_payload(row)["update_time"] == "2026-01-01"


def test_business_breakdown_text_and_payload():
    row = {
        "name": "n", "code": "c", "date": "2026-01-01",
        "category_type": "按产品", "category_name": "白酒",
        "revenue": 1.0, "revenue_ratio": 0.5, "cost": 0.4, "cost_ratio": 0.4,
        "profit": 0.6, "profit_ratio": 0.6, "gross_margin": 0.6,
    }
    text = build_business_breakdown_text(row)
    assert "按产品" in text and "白酒" in text
    payload = get_business_breakdown_payload(row)
    assert payload["revenue"] == 1.0 and payload["gross_margin"] == 0.6
