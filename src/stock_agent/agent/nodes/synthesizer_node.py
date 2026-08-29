# agent/nodes/synthesizer_node.py
from typing import Any, Dict

from event.decorator import node
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek


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

    model_name = "deepseek-chat"
    llm = get_deepseek(model=model_name, temperature=0.1)
    
    final_prompt = f"""
        你是一个严谨的A股投资顾问。
        结合以下所有信息，给出专业投资分析报告。

        数据：
        - 技术面：{state.get("stock_technique_factor", [])}
        - 基本面：{state.get("stock_financial_factor", [])}
        - 新闻分析：{state.get("news_analysis", "")}
        - 用户问题：{state.get("user_question", "")}
        - 中长记忆: {state.get("memory_context", "")}

        生成要求（必须遵守）：
        1. 所有财务、技术、新闻相关的数字与结论必须来自上面给出的数据，禁止编造或外推；
        2. 数据中没有的指标或信息，明确写"数据缺失"，不要用模型自身知识猜测填充；
        3. 关键结论尽量注明数据来源（技术面/基本面/新闻）；
        4. 不要把模型记忆中的个股数据当作检索结果写入报告。

        严格按照以下 JSON Schema 输出：
        {InvestmentRecommendation.model_json_schema()}
    """

    # 使用结构化输出
    structured_llm = llm | JsonOutputParser(pydantic_object=InvestmentRecommendation)
    if "reflections" in state.keys() and len(state["reflections"]) > 0:
        final_prompt = final_prompt + """
        **之前的 Reflection 反馈（必须重视）**：
        {reflections}

        请根据 Reflection 改进输出。
        """.format(reflections=state["reflections"])
    
    recommendation: InvestmentRecommendation = invoke_with_metrics(
            structured_llm,
            [SystemMessage(content=final_prompt)],
            "synthesizer",
            model_name
        )

    return {
        "final_answer": recommendation["markdown_report"],
        "messages": [SystemMessage(content=str(recommendation))]
    }
