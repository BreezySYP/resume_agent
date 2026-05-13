"""
agents/base.py
构建 Researcher / Coder / Reviewer 三个 Agent。
每个 Agent 通过工厂函数创建，便于后续单独替换模型或工具。
"""
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama

from configs.settings import OLLAMA_URL, LLM_MODEL
from rag.tools import researcher_tools, coder_tools, reviewer_tools

print("preparing llm...")

# 共用的 LLM 实例（Agent 内部推理）
llm = ChatOllama(
    model=LLM_MODEL,
    temperature=0.2,
    num_ctx=8192,
    num_gpu=999,
    base_url=OLLAMA_URL,
)

print("✅ llm ready")

def build_researcher():
    return create_agent(
        model=llm,
        tools=researcher_tools,
        system_prompt=SystemMessage(content=(
            "你是技术研究员，擅长查找最新最佳实践和技术方案。\n"
            "请先调用 rag_search 检索本地知识库；"
            "如果内容不足或需要最新信息，再调用 tavily_search 实时搜索。"
        )),
    )


def build_coder():
    return create_agent(
        model=llm,
        tools=coder_tools,
        system_prompt=SystemMessage(content=(
            "你是资深 Python/C# 开发者，擅长编写高质量、可维护的代码。\n"
            "编码前可调用 rag_search 查找相关示例或规范。"
        )),
    )


def build_reviewer():
    return create_agent(
        model=llm,
        tools=reviewer_tools,
        system_prompt=SystemMessage(content=(
            "你是严格的代码审查专家，专注于代码质量、安全性和可维护性。"
        )),
    )
