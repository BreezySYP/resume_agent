"""agents/base.py — Researcher / Coder / Reviewer 工厂"""
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from shared.models.ollama import get_llm
from rag.tools import researcher_tools, coder_tools, reviewer_tools


# def build_researcher():
#     return create_agent(
#         model=get_llm(), tools=researcher_tools,
#         system_prompt=SystemMessage(content=(
#             "你是技术研究员，擅长查找最新最佳实践和技术方案。\n"
#             "请先调用 rag_search 检索本地知识库；内容不足时再调用 tavily_search 实时搜索。"
#         )),
#     )


# def build_coder():
#     return create_agent(
#         model=get_llm(), tools=coder_tools,
#         system_prompt=SystemMessage(content=(
#             "你是资深 Python/C# 开发者，擅长编写高质量、可维护的代码。\n"
#             "编码前可调用 rag_search 查找相关示例或规范。"
#         )),
#     )


# def build_reviewer():
#     return create_agent(
#         model=get_llm(), tools=reviewer_tools,
#         system_prompt=SystemMessage(content=(
#             "你是严格的代码审查专家，专注于代码质量、安全性和可维护性。"
#         )),
#     )

def build_generalist():
    return create_agent(
        model=get_llm(), system_prompt=SystemMessage(content="你是拥有普世只会的全才，请根据用户问题用最亲和简单的语言描述一个复杂专业的问题并返回结果。")
    )