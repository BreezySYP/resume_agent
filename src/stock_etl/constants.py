DEFAULT_DAILY_STEPS = ["history", "technical", "capital_hot", "news", "qdrant_news_sync"]
DEFAULT_SEASON_STEPS = ["history", "technical", "financial_statement", "financial_feature",
                         "financial_factor", "composite", "capital_hot", "profile", "news", "qdrant_profile_sync", "qdrant_news_sync"]


STEPS_META = {
    "history":             {"label": "历史K线",  "group": "daily"},
    "technical":           {"label": "技术因子",  "group": "daily"},
    "financial_statement": {"label": "财务报表",  "group": "season"},
    "financial_feature":   {"label": "财务特征",  "group": "season"},
    "financial_factor":    {"label": "财务因子",  "group": "season"},
    "composite":           {"label": "综合因子",  "group": "season"},
    "capital_hot":         {"label": "资金热点",  "group": "daily"},
    "profile":             {"label": "公司简介",  "group": "daily"},
    "news":                {"label": "新闻",      "group": "daily"},
    "qdrant_news_sync":    {"label": "新闻向量同步", "group": "daily"},
    "qdrant_profile_sync": {"label": "简介向量同步", "group": "daily"},
}

# 单股可触发的 step（全局类 step 不支持单股）
PER_STOCK_STEPS = ["history", "financial_statement", "profile", "news"]

# 全量触发组合
DAILY_STEPS  = ["history", "technical", "capital_hot", "profile", "news",
                 "qdrant_profile_sync", "qdrant_news_sync"]
SEASON_STEPS = ["history", "technical", "financial_statement", "financial_feature",
                "financial_factor", "composite", "capital_hot", "profile", "news",
                "qdrant_profile_sync", "qdrant_news_sync"]


ETL_QUEUE_PREFIX = "pipline"
