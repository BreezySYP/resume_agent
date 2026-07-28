from typing import Any, Dict
from event.decorator import node
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek
from langchain_core.messages import SystemMessage

@node(node_name="reflection", title="反射节点")
def reflection_node(state: AgentState) -> Dict[str, Any]:
    """Reflection：让模型自我审视输出质量"""

    retry_count = state.get("retry_count", 0)
    
    if retry_count >= 2:
        return {
            "reflections": state.get("reflections", []) + ["已达最大反射次数，直接结束"],
            "retry_count": retry_count + 1,
        }

    llm = get_deepseek(temperature=0.1)
    
    prompt = f"""
        请严格评估以下投资分析输出质量：

        用户问题：{state.get("user_question", "")}
        当前计划：{state.get("plan", "")}
        当前输出：{state.get("final_answer", state.get("markdown", ""))}

        从以下维度打分（0-10）并给出改进建议：
        1. 数据一致性 2. 风险披露完整性 3. 逻辑严谨性 4. 时效性

        如果整体质量 > 8 分，输出 "PASS"。
        否则输出具体改进建议。
    """
            
    reflection = llm.invoke([SystemMessage(content=prompt)])
    
    reflection_text = reflection.content  # LLM 输出
    
    return {
        "reflections": state.get("reflections", []) + [reflection_text],
        "retry_count": retry_count + 1
    }