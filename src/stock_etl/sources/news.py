"""sources/news.py — 个股新闻抓取（东方财富新闻搜索接口）"""
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
    """东方财富-个股新闻-最近 100 条新闻"""
    inner_param = {
        "uid": "", "keyword": symbol, "type": ["cmsArticleWebOld"], "client": "web",
        "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default", "pageIndex": 1, "pageSize": 10, "preTag": "<em>", "postTag": "</em>"}},
    }
    params = {"cb": JSONP_CALLBACK, "param": json.dumps(inner_param, ensure_ascii=False), "_": str(int(time.time() * 1000))}
    resp = requests.get(NEWS_SEARCH_URL, params=params, headers=NEWS_HEADERS)
    data_json = json.loads(resp.text.strip(f"{JSONP_CALLBACK}(")[:-1])
    return pd.DataFrame(data_json["result"]["cmsArticleWebOld"])


def fetch_all_stock_news(min_code: str = "000000") -> pd.DataFrame:
    """抓取全市场（或起始代码之后）个股新闻"""
    import akshare as ak

    codes = [(r["code"], r["name"]) for r in ak.stock_info_a_code_name().to_dict("records") if r["code"] > min_code]
    frames = []
    for code, name in codes:
        news_df = stock_news(symbol=code)
        if news_df.empty:
            time.sleep(random.uniform(1, 2))
            continue
        news_df["name"] = name
        news_df["code"] = code
        news_df = news_df.drop(columns=["image"], errors="ignore")
        frames.append(news_df)
        logger.info("fetched news for {} {}", code, name)
        time.sleep(random.uniform(1, 2))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
