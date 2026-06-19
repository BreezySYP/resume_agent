from core.db import engine
import pandas as pd
import numpy as np

METRIC_MAP = {
    "营业总收入": "revenue",
    "归母净利润": "net_profit",
    "经营现金流量净额": "operating_cashflow",
    "净资产收益率(ROE)": "roe",
    "总资产报酬率(ROA)": "roa",
    "资产负债率": "leverage",
}


def load_data():
    sql = """
    SELECT *
    FROM financial_statement
    """
    df = pd.read_sql(sql, engine)
    
    # 确保日期格式正确并排序
    df['report_date'] = pd.to_datetime(df['report_date'])
    df = df.sort_values(["code", "report_date"]).reset_index(drop=True)
    
    return df


def build_features(df: pd.DataFrame):
    df = df.copy()

    # =========================
    # 1. 成长性指标（推荐使用同比 YoY）
    # =========================
    # 同比增长率（YoY）：往前推4个季度
    for col, growth_col in [
        ("revenue", "revenue_growth"),
        ("net_profit", "profit_growth")
    ]:
        # 计算上一年同期值
        df[f'prev_year_{col}'] = df.groupby("code")[col].shift(4)
        
        # 计算同比增长率
        df[growth_col] = (df[col] - df[f'prev_year_{col}']) / df[f'prev_year_{col}']
        df[growth_col] = (df[growth_col] * 100).round(4)   # 转成百分比，保留4位小数

    # 同时保留环比增长率（可选）
    df["revenue_growth_qoq"] = df.groupby("code")["revenue"].pct_change() * 100
    df["profit_growth_qoq"] = df.groupby("code")["net_profit"].pct_change() * 100
    df["revenue_growth_qoq"] = df["revenue_growth_qoq"].round(4)
    df["profit_growth_qoq"] = df["profit_growth_qoq"].round(4)

    # =========================
    # 2. 现金流质量
    # =========================
    df["fcf_ratio"] = df["operating_cashflow"] / df["net_profit"]

    # =========================
    # 3. 杠杆相关
    # =========================
    if "asset_liability_ratio" in df.columns:
        df["leverage_score"] = 1 / (1 + df["asset_liability_ratio"])

    # =========================
    # 4. 盈利质量综合指标
    # =========================
    df["quality_score"] = (
        df.get("roe", 0) * 0.4 +
        df.get("net_margin", 0) * 0.3 +
        df["fcf_ratio"].fillna(0) * 0.3
    )

    # =========================
    # 5. 清理异常值
    # =========================
    df.replace([float("inf"), -float("inf"), np.inf, -np.inf], np.nan, inplace=True)
    
    # 可选：删除辅助列（看你需求）
    # drop_cols = [col for col in df.columns if col.startswith('prev_year_')]
    # df = df.drop(columns=drop_cols)

    return df


def save(df):
    df.to_sql(
        "financial_feature",
        engine,
        if_exists="replace",   # 或者用 'append' 如果是增量更新
        index=False,
        chunksize=1000,
        method='multi'
    )
    print(f"✅ 已成功保存 {len(df)} 条记录到 financial_feature 表")


def run():
    print("🚀 开始加载数据...")
    df = load_data()
    print(f"加载完成，共 {len(df)} 条记录")

    print("🔧 正在计算特征...")
    df_feat = build_features(df)

    print("💾 正在保存到 financial_feature 表...")
    save(df_feat)

    # 简单验证增长率
    print("\n📊 增长率计算结果预览：")
    print(df_feat[['code', 'report_date', 'revenue', 'revenue_growth', 
                   'net_profit', 'profit_growth']].tail(8))


if __name__ == "__main__":
    run()