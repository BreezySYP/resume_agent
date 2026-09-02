"""eval.context_text.parse_repr 单测：RAG 字符串 repr / JSON 解析。"""
from eval.context_text import parse_repr

REAL_NEWS_REPR = (
    "{'title': '兆易创新(<em>603986</em>.<em>SH)2<em>0</em>2<em>6</em>年中报净利润为<em>68</em>.57亿元、"
    "较去年同期上涨1<em>09</em>1.5<em>0</em>%', "
    "'content': '2026年8月19日，兆易创新(603986.SH)发布2026年中报。\\u3000\\u3000公司营业总收入为115.66亿元，"
    "较去年同报告期营业总收入增加74.15亿元，实现3年连续上涨，同比较去年同期上涨178.67%。', "
    "'summary': None, 'date': '2026-08-19 10:15:07', "
    "'fetch_time': Timestamp('2026-08-19 10:15:07'), "
    "'url': 'http://finance.eastmoney.com/a/202608193845843755.html', "
    "'source_type': 'news', 'sector': None, 'importance_score': 0.5}"
)


def test_parse_repr_plain_text_is_none():
    assert parse_repr("普通文本") is None
    assert parse_repr("http://finance.eastmoney.com/a.html") is None
    assert parse_repr("") is None


def test_parse_repr_news_dict_repr():
    parsed = parse_repr(REAL_NEWS_REPR)
    assert isinstance(parsed, dict)
    assert set(parsed) == {
        "title",
        "content",
        "summary",
        "date",
        "fetch_time",
        "url",
        "source_type",
        "sector",
        "importance_score",
    }
    assert parsed["fetch_time"] is None
    assert parsed["summary"] is None
    assert parsed["date"] == "2026-08-19 10:15:07"


def test_parse_repr_json():
    assert parse_repr('{"code": "002419", "title": "新闻"}') == {
        "code": "002419",
        "title": "新闻",
    }
    assert parse_repr('[{"id": 1}, {"id": 2}]') == [{"id": 1}, {"id": 2}]


def test_parse_repr_invalid_json_is_none():
    assert parse_repr("{'truncated': '...") is None
    assert parse_repr("[1, 2") is None
