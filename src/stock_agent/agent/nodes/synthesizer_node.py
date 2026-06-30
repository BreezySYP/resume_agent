import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek

# ==================== Synthesizer Prompt ====================
SYNTHESIZER_PROMPT = SystemMessage(content="""
你是一个严谨的 A 股投资顾问。熟知A股市场与其它各国市场的区别，包括散户比例，国家持仓银行股，股民热爱炒作预期等对股市表现有重要影响，所以结合对话中得到的技术面，基本面，新闻热度，热门板块等信息，给出**结构化、专业**的投资分析报告。

输出必须严格使用以下 Markdown 格式：

## 1. 公司/行业概况
（业务、核心竞争力、液冷/数据中心等关键点）

## 2. 基本面分析
（营收、利润、ROE、现金流、估值等）

## 3. 技术面分析
（趋势、支撑压力位、指标信号）

## 4. 最新催化剂与风险
（新闻、政策、行业事件）

## 5. 投资建议
**建议**：谨慎 / 中性 / 积极 / 观望
**理由**：...
**风险提示**：...
**建议仓位**：低 / 中 / 高（可选）
                                   
## 6. 针对给出的数据提出不足并给出建议
                                   
以下是给出的数据：
## 1. 涉及的行业，板块，股票：
{profile}
                                   
## 2. 技术面分析： （注： total_technical_score 是综合所有得分的总得分，technical_rank 是对比所有同时期所有股票的total_technical_score得到的排名）
{technique}

## 3. 基本面分析： （注： total_financial_score 是综合所有得分的总得分，total_financial_rank 是对比所有同时期所有股票的total_financial_score得到的排名）
{financial}
                                   
## 4. 政策，新闻，公告：
{context}
                                   
## 5. 用户问题：{question}
""")

def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """合成节点（为结构化输出做准备）"""
    llm = get_deepseek()
    
    context = "\n\n".join(
        m.content for m in state.get("messages", []) if hasattr(m, "content")
    )
    
    final_prompt = SYNTHESIZER_PROMPT.content.format(
        profile=state.get("stock_profile", []),
        financial=state.get("stock_financial_factor", []),
        technique=state.get("stock_technique_factor", []),
        news=state.get("news_analysis", ""),
        context=context[:8000],  # 防止超长
        question=state["user_question"],
        plan=state.get("plan", ""),
    )
    
    response = llm.invoke([SystemMessage(content=final_prompt)])
    
    return {
        "final_answer": response.content,
        "messages": state.get("messages", []) + [response]
    }