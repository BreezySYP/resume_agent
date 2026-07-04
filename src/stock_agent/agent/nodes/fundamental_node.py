import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
import pandas as pd
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.code_rule import add_prefix
from shared.db.mysql import engine
from shared.models.deepseek import get_deepseek


FINANCIAL_FACTOR_EXPLAIN = """
    数学公式总结
    基础定义
    revenue = 营业收入（TTM，过去12个月）
    net_profit = 归母净利润（TTM）
    roe = 净资产收益率（%）
    roa = 总资产收益率（%）
    net_margin = 销售净利率（%）
    operating_cashflow = 经营活动现金流净额
    asset_liability_ratio = 资产负债率（%）
    report_date = 财报报告期（通常为季报，每年3/6/9/12月）

    一、基础指标计算
    1. 同比增长率（YoY Growth）
    text
    revenue_growth = (revenue_t / revenue_{t-4} - 1) × 100
    profit_growth = (net_profit_t / net_profit_{t-4} - 1) × 100

    其中：
    t = 当前报告期
    t-4 = 4个季度前的同一报告期（去年同期）
    含义：营业收入和净利润相对于去年同期的增长百分比。>0表示增长，<0表示下滑。

    2. 环比增长率（QoQ Growth）
    text
    revenue_growth_qoq = (revenue_t / revenue_{t-1} - 1) × 100
    profit_growth_qoq = (net_profit_t / net_profit_{t-1} - 1) × 100

    其中：
    t-1 = 上一个报告期（上季度）
    含义：营业收入和净利润相对于上一个季度的增长百分比，反映短期变化趋势。

    3. 自由现金流比率（FCF Ratio）
    text
    fcf_ratio = operating_cashflow / net_profit
    含义：每单位净利润对应的经营现金流，衡量盈利质量。>1表示盈利有真实现金支撑，<1可能盈利质量较差（如大量应收账款）。

    注意：若净利润为负，该值为负数；若为无穷大（净利润=0），处理后为NaN。

    4. 杠杆评分（Leverage Score）
    text
    leverage_score = 1 / (1 + asset_liability_ratio)

    其中：
    asset_liability_ratio 以小数形式表示（如0.5表示50%资产负债率）
    含义：资产负债率越低，得分越高（接近1），表示财务杠杆风险越小。

    5. 质量评分（Quality Score - 初步）
    text
    quality_score = ROE × 0.4 + net_margin × 0.3 + fcf_ratio × 0.3
    含义：综合盈利能力（ROE）、利润率（净利率）和盈利质量（现金流），初步评估公司质量。

    注意：该评分在后续build_financial_factor中被重新定义为纯现金流质量指标。

    二、百分位排名计算
    text
    对于每个财务指标X，在同一个报告日期内，对所有股票计算：

    X_rank = (X值从小到大排序后的排名位置 - 1) / (当日股票总数 - 1)
    含义：0-1之间的百分位排名，越接近1表示该指标在当期所有股票中表现越好。

    三、综合评分计算
    Profitability Score（盈利能力得分）
    text
    Profitability_Score = ROE_rank × 0.5 
                        + ROA_rank × 0.2 
                        + Net_Margin_rank × 0.3
    含义：综合衡量企业赚钱能力，权重偏向ROE（净资产收益率），代表股东回报率。得分越高，盈利能力越强。

    Growth Score（成长性得分）
    text
    Growth_Score = Revenue_Growth_rank × 0.4 
                + Profit_Growth_rank × 0.6
    含义：综合衡量企业成长性，权重偏向净利润增长，因为净利润增长更能体现企业盈利能力的提升。得分越高，成长性越好。

    Quality Score（盈利质量得分）
    text
    Quality_Score = FCF_Ratio_rank
    含义：纯现金流质量评价。FCF比率越高（现金流越充沛），得分越高，表示盈利有真实的现金支撑，质量更好。

    Safety Score（安全性得分）
    text
    Safety_Score = 1 - Asset_Liability_Ratio_rank
    含义：财务安全性评价。资产负债率越低（排名越靠前，_rank越接近1），得分越接近1，表示财务结构更稳健、偿债风险更低。

    Total Financial Score（总财务得分）
    text
    Total_Financial_Score = Profitability_Score × 0.35 
                        + Growth_Score × 0.35 
                        + Quality_Score × 0.15 
                        + Safety_Score × 0.15
    含义：综合财务面评价：

    盈利能力（35%）：企业赚钱能力

    成长性（35%）：收入利润增长能力

    盈利质量（15%）：现金流支撑程度

    安全性（15%）：财务杠杆风险

    得分越高，整体财务基本面越好。

    Total Financial Rank（财务排名）
    text
    Total_Financial_Rank = 按Total_Financial_Score从高到低排序，得分最高的排名为1
    含义：每个报告期在所有股票中的财务排名，数值越小表示财务基本面越强（排名越靠前）。

    输出字段速查表
    字段	取值范围	含义
    profitability_score	0 ~ 1	盈利能力得分，越高表示ROE/ROA/净利率越好
    growth_score	0 ~ 1	成长性得分，越高表示营收/利润增长越快
    quality_score	0 ~ 1	盈利质量得分，越高表示现金流越充沛
    safety_score	0 ~ 1	安全性得分，越高表示资产负债率越低
    total_financial_score	0 ~ 1	综合财务得分，越高表示整体财务基本面越好
    total_financial_rank	1 ~ N（N为当期股票数）	当期财务排名，1表示财务基本面最强
    关键注意事项
    时间口径一致性：所有指标都在同一个report_date截面比较（季报日期对齐）

    增长率计算：使用shift(4)确保同比（去年同期），pct_change()计算环比（上季度）

    数据处理：np.inf和-np.inf被替换为NaN，避免计算错误

    财务频率：每年3、6、9、12月有财报数据，其他月份可能为缺失值
"""

def fundamental_node(state: AgentState) -> Dict[str, Any]:
    """基本面 - 纯数据节点"""
    if not state.get("stock_profile"):
        return {"stock_financial_factor": []}
    
    try:
        codes = [add_prefix(p["code"]) for p in state["stock_profile"]]
        sql = f"""
            SELECT t.* FROM financial_factor t
            JOIN (
                SELECT code, MAX(report_date) AS max_date 
                FROM financial_factor 
                WHERE code IN ({str(codes)[1:-1]}) 
                GROUP BY code
            ) latest ON t.code = latest.code AND t.report_date = latest.max_date;
        """
        df = pd.read_sql(sql, engine.connect()).round(2)
        return {"stock_financial_factor": df.to_dict(orient="records")}
    except Exception as e:
        return {"stock_financial_factor": [], "error": str(e)}