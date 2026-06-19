import random

import requests
import pandas as pd
import datetime, random, time
from core.db import engine, insert_ignore
import json
import tushare as ts
import akshare as ak

from shared.configs.settings import REDIS_URL
from shared.models.ollama import get_embedding
from langchain_redis import RedisVectorStore
from loguru import logger

tushare_token = "3a0c335ba42e85deab34623d62caf391e5edccebcc239f393db3b5d0"

def fetch_announcements(code=None, days=30):
    print("正在获取最新公告...")
    # 这里使用东财或巨潮接口（简化版示例）
    url = "https://np-list.eastmoney.com/api/search"
    # 实际项目中推荐用 Tushare pro.announcement() 或爬取巨潮资讯
    
    # 以下为示例结构（你需要根据真实接口调整）
    params = {
        "type": "announcement",
        "days": days,
        # "code": code
    }
    
    try:
        # 这里先用占位数据，后面可以换真实接口
        # 真实采集推荐：Tushare 或 requests 爬取巨潮
        data = []  # 替换为真实请求结果
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.to_sql('announcements', engine, if_exists='append', index=False)
            print(f"✅ 公告保存成功，共 {len(df)} 条")
    except Exception as e:
        print(f"公告采集失败: {e}")


def parse_announcement_with_llm(title, content):
    """用 LLM 提取关键实体（后续接入你的 LLM）"""
    # 示例返回格式
    return {
        "category": "业绩预告", 
        "key_points": ["预计净利润增长50%", "扣非净利润提升"],
        "impact": "正面"
    }


def stock_news(symbol):
    """
    东方财富-个股新闻-最近 100 条新闻
    https://so.eastmoney.com/news/s?keyword=603777
    :param symbol: 股票代码
    :type symbol: str
    :return: 个股新闻
    :rtype: pandas.DataFrame
    """
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_param = {
        "uid": "",
        "keyword": symbol,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": 10,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    params = {
        "cb": "jQuery35101792940631092459_1764599530165",
        "param": json.dumps(inner_param, ensure_ascii=False),  # 保留中文,
        "_": "1764599530176",
    }
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
        "cache-control": "no-cache",
        "connection": "keep-alive",
        "cookie": "qgqp_b_id=652bf4c98a74e210088f372a17d4e27b; st_nvi=ulN5JAj9FUocz3p4klMME9f20; emshistory=%5B%22603777%22%5D; nid18=010d039dd427dc4d187090491f47d7ad; nid18_create_time=1764582801999; gviem=gSdeY51VWSuTzM3kWaagtf560; gviem_create_time=1764582801999; st_si=55269775884615; st_pvi=66803244437563; st_sp=2025-11-19%2014%3A19%3A16; st_inirUrl=https%3A%2F%2Fso.eastmoney.com%2Fnews%2Fs; st_sn=2; st_psi=20251201223210488-118000300905-0940816858; st_asi=delete",
        "host": "search-api-web.eastmoney.com",
        "pragma": "no-cache",
        "referer": "https://so.eastmoney.com/news/s?keyword=603777",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "script",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_text = r.text
    data_json = json.loads(
        data_text.strip("jQuery35101792940631092459_1764599530165(")[:-1]
    )
    temp_df = pd.DataFrame(data_json["result"]["cmsArticleWebOld"])
    # temp_df["url"] = "http://finance.eastmoney.com/a/" + temp_df["code"] + ".html"
    # temp_df.rename(
    #     columns={
    #         "date": "发布时间",
    #         "mediaName": "文章来源",
    #         "code": "-",
    #         "title": "新闻标题",
    #         "content": "新闻内容",
    #         "url": "新闻链接",
    #         "image": "-",
    #     },
    #     inplace=True,
    # )
    # temp_df["关键词"] = symbol
    # temp_df = temp_df[
    #     [
    #         "关键词",
    #         "新闻标题",
    #         "新闻内容",
    #         "发布时间",
    #         "文章来源",
    #         "新闻链接",
    #     ]
    # ]
    # temp_df["新闻标题"] = (
    #     temp_df["新闻标题"]
    #     .str.replace(r"\(<em>", "", regex=True)
    #     .str.replace(r"</em>\)", "", regex=True)
    # )
    # temp_df["新闻标题"] = (
    #     temp_df["新闻标题"]
    #     .str.replace(r"<em>", "", regex=True)
    #     .str.replace(r"</em>", "", regex=True)
    # )
    # temp_df["新闻内容"] = (
    #     temp_df["新闻内容"]
    #     .str.replace(r"\(<em>", "", regex=True)
    #     .str.replace(r"</em>\)", "", regex=True)
    # )
    # temp_df["新闻内容"] = (
    #     temp_df["新闻内容"]
    #     .str.replace(r"<em>", "", regex=True)
    #     .str.replace(r"</em>", "", regex=True)
    # )
    # temp_df["新闻内容"] = temp_df["新闻内容"].str.replace(r"\u3000", "", regex=True)
    # temp_df["新闻内容"] = temp_df["新闻内容"].str.replace(r"\r\n", " ", regex=True)
    return temp_df

from langchain_chroma import Chroma

def vector_store():
    # 最简配置 + 强制短超时
    embedding  = get_embedding()
    persist_directory = "./data/chroma_db"
    store = Chroma(
                embedding_function=embedding,
                persist_directory=persist_directory,
                collection_name="market_news_global",
            )
    print("✅ VectorStore 初始化完成")
    return store

import shortuuid

if __name__ == "__main__":
    # df = ak.stock_news_em(symbol="000001")   # 平安银行最新新闻

    codes = [(r["code"], r["name"]) for r in ak.stock_info_a_code_name().to_dict("records") if r["code"] > '603922']
    # service = StockNewsService()
    store = vector_store()
    for code, name in codes:
        news_df = stock_news(symbol=code)
        news_df["name"] = name  
        news_df["code"] = code
        news_df = news_df.drop(columns=["image"])
        # news_df["unique_id"] = news_df["code"].astype(str) + "_" + news_df["date"].astype(str)
        news_df.to_sql('stock_news', engine, if_exists='append', index=False)
        
        logger.info(f"saved news for {code}")
        # for _, row in news_df.iterrows():
        #     text = f"【{row['code']} {row['name']}】{row['title']}\n{row['content']}"
        #     metadata = {
        #         "unique_id": shortuuid.ShortUUID().random(length=10),
        #         "code": row['code'],
        #         "date": row['date'],
        #         "mediaName": row['mediaName'],
        #     }
        #     store.add_texts(texts=[text], metadatas=[metadata], ids=[metadata["unique_id"]])
        time.sleep(random.uniform(1, 2)) 

 