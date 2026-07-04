"""sources/news.py — 个股新闻抓取"""
import json
import random
import time

import pandas as pd
import requests
from loguru import logger

NEWS_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
NEWS_HEADERS = {
    "accept": "*/*",
    "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
    "referer": "https://so.eastmoney.com/news/s",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}
JSONP_CALLBACK = "jQuery35101792940631092459_1764599530165"


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