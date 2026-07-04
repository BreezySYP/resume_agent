import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.code_rule import  remove_prefix
from shared.db.mysql import engine

TECHNICAL_EXPLAIN = f"""
    数学公式总结
    基础定义
    close = 每日收盘价序列
    high = 每日最高价 | low = 每日最低价 | volume = 每日成交量

    一、基础指标计算
    1. RSI（相对强弱指标）
    text
    RSI = 100 - 100 / (1 + RS)

    其中：
    RS = SMA(G, 14) / SMA(L, 14)
    G = max(close_t - close_(t-1), 0)     → 当日上涨幅度
    L = max(close_(t-1) - close_t, 0)     → 当日下跌幅度
    SMA(x, n) = 滚动n期算术平均值
    含义：衡量近期价格涨跌力度，0-100之间，>70超买，<30超卖。

    2. Momentum（动量）
    text
    MOM20 = close_t / close_(t-20) - 1
    含义：当前收盘价相对于20个交易日前的涨幅百分比。

    3. OBV（能量潮/平衡交易量）
    text
    OBV_t = Σ(sign(Δclose) × volume_t)

    其中：
    Δclose = close_t - close_(t-1)
    sign(Δclose) =  1  , 若 Δclose > 0（上涨日）
                -1  , 若 Δclose < 0（下跌日）
                    0  , 若 Δclose = 0（平盘）
    含义：累积资金流向，上涨日加成交量，下跌日减成交量。上升趋势表示资金净流入。

    4. MFI（资金流量指标）
    text
    MFI = 100 - 100 / (1 + MFR)

    其中：
    TP = (high + low + close) / 3                    → 当日典型价格
    MF = TP × volume                                 → 当日资金流量
    MFR = Σ(Positive_MF, 14) / Σ(Negative_MF, 14)   → 资金比率

    Positive_MF = MF  , 若 ΔTP > 0（TP较前日上升）
                0   , 若 ΔTP ≤ 0

    Negative_MF = MF  , 若 ΔTP < 0（TP较前日下降）
                0   , 若 ΔTP ≥ 0
    含义：带成交量的RSI，0-100之间，衡量资金流入流出强度。

    5. MACD Histogram（MACD柱状线）
    text
    MACD_Hist = MACD_Line - Signal_Line

    其中：
    MACD_Line = EMA(close, 12) - EMA(close, 26)
    Signal_Line = EMA(MACD_Line, 9)
    EMA(x, span) = 指数移动平均（span为周期）
    含义：MACD线与信号线的差值，>0表示短期动能强于长期，看涨信号。

    6. 均线比率
    text
    MA20_ratio = close / MA(close, 20)
    MA60_ratio = close / MA(close, 60)
    MA120_ratio = close / MA(close, 120)

    MA(x, n) = (x_t + x_(t-1) + ... + x_(t-n+1)) / n  → 简单移动平均
    含义：收盘价相对于不同周期均线的位置。>1表示价格在均线之上（多头），<1表示在均线之下（空头）。

    二、百分位排名计算
    text
    对于每个指标X，在同一个交易日期内，对所有股票计算：

    X_rank = (X值从小到大排序后的排名位置 - 1) / (当日股票总数 - 1)
    含义：0-1之间的百分位排名，越接近1表示该指标在当日所有股票中表现越好（排名越高）。

    三、综合评分计算
    Trend Score（趋势得分）
    text
    Trend_Score = MA20_ratio_rank × 0.3 
                + MA60_ratio_rank × 0.3 
                + MA120_ratio_rank × 0.4
    含义：衡量价格相对于短、中、长期均线的综合趋势强度，权重偏向长期均线(MA120)。得分越高，中长期趋势越强。

    Momentum Score（动量得分）
    text
    Momentum_Score = RSI14_rank × 0.3 
                + MOM20_rank × 0.4 
                + MACD_hist_rank × 0.3
    含义：综合短期超买超卖、中期价格动量、MACD动能，权重偏重20日动量。得分越高，短期上涨动能越强。

    Volume Score（成交量得分）
    text
    Volume_Score = OBV_rank × 0.5 
                + MFI14_rank × 0.5
    含义：综合资金流向累积(OBV)和资金流入强度(MFI)，等权重。得分越高，资金流入意愿越强。

    Total Technical Score（总技术得分）
    text
    Total_Technical_Score = Trend_Score × 0.4 
                        + Momentum_Score × 0.4 
                        + Volume_Score × 0.2
    含义：综合技术面评价，趋势和动量各占40%（主导），成交量占20%（辅助）。得分越高，整体技术面越好。

    Technical Rank（技术排名）
    text
    Technical_Rank = 按Total_Technical_Score从高到低排序，得分最高的排名为1
    含义：每日在所有股票中的技术面排名，数值越小表示当日技术面越强（排名越靠前）。

    输出字段速查表
    字段	取值范围	含义
    trend_score	0 ~ 1	趋势得分，越高表示中长期上升趋势越明确
    momentum_score	0 ~ 1	动量得分，越高表示短期上涨动能越强
    volume_score	0 ~ 1	成交量得分，越高表示资金流入越积极
    total_technical_score	0 ~ 1	综合技术得分，越高表示整体技术面越好
    technical_rank	1 ~ N（N为当日股票数）	当日技术排名，1表示技术面最强
        """

def technical_node(state: AgentState) -> Dict[str, Any]:
    """技术面 - 纯数据节点"""
    if not state.get("stock_profile"):
        return {"stock_technique_factor": []}
    
    try:
        codes = [int(remove_prefix(p["code"])) for p in state["stock_profile"]]
        sql = f"""
            SELECT t.* FROM technical_factor t
            JOIN (
                SELECT code, MAX(date) AS max_date 
                FROM technical_factor 
                WHERE code IN ({str(codes)[1:-1]}) 
                GROUP BY code
            ) latest ON t.code = latest.code AND t.date = latest.max_date;
        """
        df = pd.read_sql(sql, engine.connect()).round(2)

        

        return {"stock_technique_factor": df.to_dict(orient="records")}
    except Exception as e:
        return {"stock_technique_factor": [], "error": str(e)}