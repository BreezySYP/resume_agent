"""sources/news.py — 个股新闻抓取"""
import json
import random
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

NEWS_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
NEWS_HEADERS = {
    "accept": "*/*",
    "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
    "referer": "https://so.eastmoney.com/news/s",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}
JSONP_CALLBACK = "jQuery35101792940631092459_1764599530165"
NEWS_DETAIL_TIMEOUT = 10


def _extract_article_text(html_text: str) -> str:
    """从东方财富文章页提取正文：取 #ContentBody，丢弃表格（投研表格等）与脚本/广告，
    保留段落文本，段落间以换行分隔。"""
    soup = BeautifulSoup(html_text, "html.parser")
    body = soup.find(id="ContentBody") or soup.find("div", class_="txtinfos")
    if body is None:
        body = soup

    # 去掉表格、脚本、样式、图片与顶部"妙想"推广链接
    for tag in body.find_all(["table", "script", "style", "noscript", "img"]):
        tag.decompose()
    for tag in body.find_all("a", class_="toplink"):
        tag.decompose()

    lines = []
    for p in body.find_all("p"):
        text = p.get_text("", strip=True)
        if text:
            lines.append(text)
    if not lines:
        # 兜底：无 <p> 时取 body 全部文本
        text = body.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def fetch_article_content(url: str) -> str:
    """抓取新闻详情页并提取正文；失败返回空串（由调用方决定是否回退原内容）。"""
    try:
        resp = requests.get(url, headers=NEWS_HEADERS, timeout=NEWS_DETAIL_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return _extract_article_text(resp.text)
    except Exception as e:
        logger.warning("fetch news detail failed url={}: {}", url, e)
        return ""


def stock_news(symbol: str) -> pd.DataFrame:
    inner_param = {
        "uid": "", "keyword": symbol, "type": ["cmsArticleWebOld"], "client": "web",
        "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default", "pageIndex": 1, "pageSize": 10, "preTag": "<em>", "postTag": "</em>"}},
    }
    params = {"cb": JSONP_CALLBACK, "param": json.dumps(inner_param, ensure_ascii=False), "_": str(int(time.time() * 1000))}
    resp = requests.get(NEWS_SEARCH_URL, params=params, headers=NEWS_HEADERS)
    data_json = json.loads(resp.text.strip(f"{JSONP_CALLBACK}(")[:-1])
    return pd.DataFrame(data_json["result"]["cmsArticleWebOld"])


def fetch_stock_news(code, name):
    """code format is 000001"""
    news_df = stock_news(symbol=code)
    news_df["name"] = name
    news_df["code"] = code
    news_df = news_df.drop(columns=["image"], errors="ignore")
    # 搜索接口的 content 是带 HTML 标签/表格的摘要片段，替换为详情页正文（失败则保留原值）
    if {"url", "content"}.issubset(news_df.columns):
        parsed_contents = []
        for url, original in zip(news_df["url"], news_df["content"]):
            text = fetch_article_content(url) if isinstance(url, str) and url else ""
            if not text:
                text = original if isinstance(original, str) else ""
            parsed_contents.append(text)
        news_df["content"] = parsed_contents
    logger.info("fetched news for {} {}", code, name)
    return news_df


def fetch_all_stock_news(min_code: str = "000000", on_batch=None, batch_size: int = 100) -> None:
    """逐批抓取个股新闻。每 batch_size 只股票后调用 on_batch(df, last_code)：
    调用方负责在 on_batch 里先存 DB 再更新 checkpoint。
    """
    import akshare as ak

    codes = [(r["code"], r["name"]) for r in ak.stock_info_a_code_name().to_dict("records") if r["code"] > min_code]

    frames = []
    last_code = None
    for code, name in codes:
        news_df = fetch_stock_news(code, name)
        last_code = code
        if not news_df.empty:
            frames.append(news_df)

        if on_batch and len(frames) >= batch_size and last_code:
            on_batch(pd.concat(frames, ignore_index=True), last_code)
            frames = []

        time.sleep(random.uniform(1, 2))

    if on_batch and frames and last_code:
        on_batch(pd.concat(frames, ignore_index=True), last_code)

if __name__ == "__main__":
    result = (fetch_stock_news("001229", "魅视科技"))
    print(result)
