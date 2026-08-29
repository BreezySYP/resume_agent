"""stock_etl/sources/news.py 单测：详情页正文提取（跳过表格/广告）与 content 替换。"""
import pandas as pd
from sources import news

ARTICLE_HTML = """<div class="contentwrap">
    <div class="txtinfos" id="ContentBody">
        <p>　　<a class="toplink" target="_blank" href="https://ai.eastmoney.com/x">全新妙想投研助理，立即体验</a></p>
        <p>　　近5日机构合计调研203家公司，<span id="stock_0.002353"><a href="http://quote.eastmoney.com/r/0.002353" class="keytip" data-code="002353">杰瑞股份</a></span>、<span id="stock_1.688376"><a href="http://quote.eastmoney.com/r/1.688376" class="keytip" data-code="688376">美埃科技</a></span>等被多家机构扎堆调研。</p>
        <p>　　机构调研榜单中，<a class="em_stock_key_common" href="http://quote.eastmoney.com/r/0.002353">杰瑞股份</a>最受关注，参与调研的机构达到255家。</p>
        <p>　　近5日机构调研股一览</p>
        <table border="0"><tbody><tr><th>证券代码</th><th>证券简称</th><th>机构调研次数</th></tr><tr><td>002353</td><td>杰瑞股份</td><td>2</td></tr></tbody></table>
        <p class="em_media">（文章来源：证券时报网）</p>
    </div>
</div>"""


def test_extract_article_text_skips_table_and_ad():
    text = news._extract_article_text(ARTICLE_HTML)
    assert text == (
        "近5日机构合计调研203家公司，杰瑞股份、美埃科技等被多家机构扎堆调研。\n"
        "机构调研榜单中，杰瑞股份最受关注，参与调研的机构达到255家。\n"
        "近5日机构调研股一览\n"
        "（文章来源：证券时报网）"
    )
    assert "<em>" not in text
    assert "证券代码" not in text
    assert "002353" not in text
    assert "妙想" not in text


def test_extract_article_text_fallback_without_contentbody():
    html = "<html><body><div><p>第一段正文</p><p>第二段正文</p></div></body></html>"
    assert news._extract_article_text(html) == "第一段正文\n第二段正文"


def test_extract_article_text_table_only_returns_empty():
    html = '<div id="ContentBody"><table><tr><td>1</td><td>2</td></tr></table></div>'
    assert news._extract_article_text(html) == ""


def test_fetch_article_content_failure_returns_empty(monkeypatch):
    def _boom(*args, **kwargs):
        raise requests_exc()

    class requests_exc(Exception):
        pass

    monkeypatch.setattr(news.requests, "get", _boom)
    assert news.fetch_article_content("http://finance.eastmoney.com/a/1.html") == ""


def test_fetch_article_content_extracts_body(monkeypatch):
    class FakeResp:
        text = ARTICLE_HTML
        encoding = "utf-8"
        apparent_encoding = "utf-8"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(news.requests, "get", lambda *a, **k: FakeResp())
    text = news.fetch_article_content("http://finance.eastmoney.com/a/1.html")
    assert text.startswith("近5日机构合计调研203家公司")


def test_fetch_stock_news_replaces_content_and_falls_back(monkeypatch):
    raw_df = pd.DataFrame(
        [
            {"url": "http://finance.eastmoney.com/a/1.html", "content": "旧摘要1", "image": None},
            {"url": "", "content": "旧摘要2", "image": None},
        ]
    )
    monkeypatch.setattr(news, "stock_news", lambda symbol: raw_df)

    class FakeResp:
        text = ARTICLE_HTML
        encoding = "utf-8"
        apparent_encoding = "utf-8"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(news.requests, "get", lambda *a, **k: FakeResp())

    result = news.fetch_stock_news("001229", "魅视科技")
    assert result["content"][0].startswith("近5日机构合计调研203家公司")
    assert result["content"][1] == "旧摘要2"  # 无 url 时保留原内容
    assert list(result.columns) == ["url", "content", "name", "code"]


def test_fetch_stock_news_keeps_original_when_fetch_fails(monkeypatch):
    raw_df = pd.DataFrame(
        [
            {"url": "http://finance.eastmoney.com/a/1.html", "content": "旧摘要", "image": None},
        ]
    )
    monkeypatch.setattr(news, "stock_news", lambda symbol: raw_df)
    monkeypatch.setattr(
        news.requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("timeout")),
    )

    result = news.fetch_stock_news("001229", "魅视科技")
    assert result["content"][0] == "旧摘要"
