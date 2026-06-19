import pandas as pd
import numpy as np
from core.db import engine
from data.coderule import add_prefix
from jobs.data_loader import load_df

def load_technical():
    df = load_df("SELECT * FROM technical_factor", "technical_factor")
    return df

def load_financial():
    df = load_df("SELECT * FROM financial_factor", "financial_factor")
    return df

def load_price_and_valuation():
    """加载价格和估值数据（PE/PB 等）"""
    sql = """
    SELECT 
        h.code, h.date, h.close,
        -- 假设你已有估值表或用以下方式计算TTM（简化版）
        NULL as pe_ttm,   -- 后续替换为真实TTM计算
        NULL as pb,
        NULL as peg
    FROM history h
    """
    return load_df(sql, "history")

def calculate_valuation_score(pe, pb, peg):
    """估值打分（越低越好）"""
    if pd.isna(pe) or pe <= 0:
        return 0.5
    score = 1.0 / (1 + np.log1p(pe)) + 1.0 / (1 + np.log1p(pb or 2))
    return np.clip(score / 2, 0, 1)

def calculate_composite_score(df, horizon='medium'):
    """动态权重"""
    weights = {
        'short':  {'tech': 0.55, 'fin': 0.30, 'val': 0.15},
        'medium': {'tech': 0.40, 'fin': 0.45, 'val': 0.15},
        'long':   {'tech': 0.25, 'fin': 0.55, 'val': 0.20}
    }
    
    w = weights.get(horizon, weights['medium'])
    
    df = df.copy()
    df['total_composite_score'] = (
        df['total_technical_score'].fillna(0.5) * w['tech'] +
        df['total_financial_score'].fillna(0.5) * w['fin'] +
        df['valuation_score'].fillna(0.5) * w['val']
    )
    
    df['composite_rank'] = df.groupby('date')['total_composite_score'].rank(
        ascending=False, method='min'
    )
    return df

def build_stock_factor():
    print("加载技术因子...")
    tech = load_technical()
    
    print("加载财务因子...")
    fin = load_financial()
    
    print("加载价格&估值...")
    price_val = load_price_and_valuation()

    # 合并（以最新可用日期对齐）
    df = tech.merge(
        fin, 
        on=['code', 'date'], 
        how='inner',
        suffixes=('_tech', '_fin')
    )
    
    df = df.merge(price_val, on=['code', 'date'], how='left')
    
    # 计算估值分
    df['valuation_score'] = df.apply(
        lambda x: calculate_valuation_score(x['pe_ttm'], x['pb'], x['peg']), axis=1
    )
    
    # 计算综合分（默认 medium）
    df = calculate_composite_score(df, horizon='medium')
    
    # 保存
    df.to_sql(
        "stock_factor",
        engine,
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi"
    )
    print(f"✅ stock_factor 保存完成，共 {len(df)} 条记录")
    return df

if __name__ == "__main__":
    build_stock_factor()
    