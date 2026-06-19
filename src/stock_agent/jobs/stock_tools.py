import pandas as pd
from jobs.data_loader import load_df
from jobs.build_stock_factor import build_stock_factor, calculate_composite_score

from jobs.data_loader import load_df
import pandas as pd

def get_latest_stock_profile(code: str):
    """单只股票最新综合画像"""
    sql = f"""
    SELECT * FROM stock_factor 
    WHERE code = {code}
    ORDER BY date DESC LIMIT 1
    """
    df = load_df(sql, "stock_factor")
    return df.iloc[0].to_dict() if not df.empty else None

def get_top_opportunities(top_n: int = 10, horizon: str = 'medium'):
    """综合排名前N（支持动态权重）"""
    sql = """
    SELECT * FROM stock_factor 
    WHERE date = (SELECT MAX(date) FROM stock_factor)
    """
    df = load_df(sql, "stock_factor")
    df = calculate_composite_score(df, horizon=horizon)   # 使用动态权重
    return df.nlargest(top_n, 'total_composite_score')

def get_hot_sectors(top_n: int = 10):
    """当前热门板块"""
    sql = f"""
    SELECT * FROM hot_sectors 
    WHERE date = (SELECT MAX(date) FROM hot_sectors)
    ORDER BY change_pct DESC 
    LIMIT {top_n}
    """
    return load_df(sql, "hot_sectors")

def analyze_stock(code: str, horizon: str = 'medium'):
    """给Agent生成分析理由"""
    profile = get_latest_stock_profile(code)
    if not profile:
        return {"error": "未找到数据"}
    
    reasons = []
    if profile.get('total_technical_score', 0) > 0.65:
        reasons.append("技术面较强")
    if profile.get('total_financial_score', 0) > 0.65:
        reasons.append("基本面良好")
    if profile.get('capital_flow_score', 0) > 0.6:
        reasons.append("主力资金净流入")
    
    return {
        "code": code,
        "composite_score": round(profile.get('total_composite_score', 0), 4),
        "rank": int(profile.get('composite_rank', 9999)),
        "reasons": reasons,
        "tech_score": profile.get('total_technical_score'),
        "fin_score": profile.get('total_financial_score')
    }

if __name__ == "__main__":
    # 构建最新因子
    build_stock_factor()
    
    # 查询
    print("=== Top 10 ===")
    top10 = get_top_opportunities(top_n=10)
    print(top10)
    
    print("\n=== 平安银行分析 ===")
    analysis = analyze_stock("000001")
    print(analysis)