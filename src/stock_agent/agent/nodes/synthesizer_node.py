# agent/nodes/synthesizer_node.py
from typing import Any, Dict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from event.decorator import node
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek
from langchain_core.output_parsers import JsonOutputParser
from agent.nodes.technical_node import TECHNICAL_EXPLAIN
from agent.nodes.fundamental_node import FINANCIAL_FACTOR_EXPLAIN

class InvestmentRecommendation(BaseModel):
    markdown_report: str = Field(..., description="给用户看的完整详尽的 Markdown 报告")
    recommendation: str = Field(..., description="投资建议：谨慎/中性/积极/观望")
    key_reasons: list[str] = Field(...)
    main_risks: list[str] = Field(...)
    suggested_position: str = Field(..., description="低/中/高")
    confidence_score: float = Field(..., ge=0, le=1)
    suggested_stocks: list[str] = Field(...)

@node(node_name="synthesizer", title="综合分析节点")
def synthesizer_node(state: AgentState) -> Dict[str, Any]:


    llm = get_deepseek(model="deepseek-chat", temperature=0.1)
    
    final_prompt = f"""
        你是一个严谨的A股投资顾问。
        结合以下所有信息，给出专业投资分析报告。

        数据：
        - 股票画像：{state.get("stock_profile", [])}
        - 技术面：{state.get("stock_technique_factor", [])}
        - 技术面计算方式： {TECHNICAL_EXPLAIN}
        - 基本面：{state.get("stock_financial_factor", [])}
        - 基本面计算方式： {FINANCIAL_FACTOR_EXPLAIN}
        - 新闻分析：{state.get("news_analysis", "")}
        - 用户问题：{state.get("user_question", "")}
        - 对话历史: {state.get("messages")}

        严格按照以下 JSON Schema 输出：
        {InvestmentRecommendation.model_json_schema()}
    """

    # 使用结构化输出
    structured_llm = llm | JsonOutputParser(pydantic_object=InvestmentRecommendation)
    if "reflections" in state.keys() and len(state["reflections"]) > 0:
        final_prompt = final_prompt + """/n
        **之前的 Reflection 反馈（必须重视）**：
        {reflections}

        请根据 Reflection 改进输出。
        """.format(reflections=state["reflections"])
    
    recommendation: InvestmentRecommendation = structured_llm.invoke([SystemMessage(content=final_prompt)])
    
    return {
        "final_answer": recommendation["markdown_report"],
        "messages": [SystemMessage(content=str(recommendation))]
    }