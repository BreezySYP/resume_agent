def build_stock_news_text(row) -> str:
    return f"""
        公司：{row['name']}
        代码：{row['code']}
        日期：{row['date']}
        标题：{row['title']}
        内容：{row['content']}
        媒体：{row['mediaName']}
        链接：{row['url']}
        """.strip()

def get_stock_news_payload(row):
    return {
        "code": row["code"],
        "name": row["name"],
        "title": row["title"],
        "date": str(row["date"]),
        "media": row["mediaName"],
        "url": row["url"],
    }

def build_business_breakdown_text(row) -> str:
    return f"""
        公司：{row['name']}
        代码：{row['code']}
        报告日期：{row['date']}
        类别类型：{row['category_type']}
        类别名称：{row['category_name']}
        营业收入：{row['revenue']}
        营业收入比例：{row['revenue_ratio']}
        成本：{row['cost']}
        成本比例：{row['cost_ratio']}
        利润：{row['profit']}
        利润比例：{row['profit_ratio']}
        毛利率：{row['gross_margin']}
        """.strip()

def get_business_breakdown_payload(row):
    return {
        "code": row["code"],
        "name": row["name"],
        "date": str(row["date"]),
        "category_type": row["category_type"],
        "category_name": row["category_name"],
        "revenue": row["revenue"],
        "revenue_ratio": row["revenue_ratio"],
        "cost": row["cost"],
        "cost_ratio": row["cost_ratio"],
        "profit": row["profit"],
        "profit_ratio": row["profit_ratio"],
        "gross_margin": row["gross_margin"],
    }

def build_stock_profile_text(row) -> str:
    return f"""
        公司：{row['name']}
        代码：{row['code']}
        业务简介：{row['business']}
        业务详情：{row['scope']}
        更新时间：{row['update_time']}
        """.strip()

def get_stock_profile_payload(row):
    return {
        "code": row["code"],
        "name": row["name"],
        "business": row["business"],
        "update_time": str(row["update_time"]),
    }
