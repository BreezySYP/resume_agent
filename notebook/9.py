from contextlib import contextmanager
from langsmith import traceable
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
import streamlit as st
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.redis import RedisSaver
from typing import TypedDict, Annotated, List, Sequence
import operator
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv(override=True)


provider = TracerProvider()

# 如果你有 Jaeger / Tempo / Grafana，可以取消注释下面这行
exporter = OTLPSpanExporter(endpoint=os.getenv("GRAFANA_URL"))
provider.add_span_processor(BatchSpanProcessor(exporter))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# ====================== LLM ======================
llm = ChatOllama(
    model="qwen2.5:14b",
    temperature=0.2,
    num_ctx=8192,
    num_gpu=999,
    base_url=os.getenv("OLLAMA_URL")
)

# ====================== State ======================


class AgentState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    next: str
    reflections: List[str]
    final_answer: str
    human_feedback: str


# Cell 3: 工具

tavily_tool = TavilySearch(
    max_results=5, search_depth="advanced", include_answer=True)


@tool
def analyze_code(code: str) -> str:
    """分析代码质量、 bug 和改进建议"""
    with tracer.start_as_current_span("analyze_code"):
        prompt = f"请分析以下代码的质量、潜在问题和改进建议：\n\n{code}"
        return llm.invoke(prompt).content


tools = [tavily_tool, analyze_code]
print("✅ 工具加载完成")

# Cell 4: Supervisor（关键修复）
supervisor_prompt = SystemMessage(content="""你是一个严格且高效的 Supervisor。

可用节点：
- Researcher：需要搜索信息或最新最佳实践时使用
- Coder：需要编写代码时使用
- Reviewer：需要审查代码时使用
- Final_Answer：当任务已经完成（代码已编写并审查通过）时使用

当前状态判断规则：
- 如果刚刚完成 Coding → 应该去 Reviewer
- 如果刚刚完成 Review → 应该去 Final_Answer
- 不要在 Reviewer 和 Reflection 之间反复循环

只返回上面4个节点(Researcher,Coder, Reviewer,Final_Answer)中的一个节点名称，不要解释。

当前对话历史：{messages}""")

    #     MAX_STEPS = 30

def supervisor_node(state: AgentState):
    with tracer.start_as_current_span("supervisor_node"):
        last_msg = state["messages"][-1].content
        print(f"supervisor_node recieved {last_msg}")
        prompt = supervisor_prompt.content.format(messages=state["messages"][-8:])  # 取最近历史
        # if len(state["messages"]) > MAX_STEPS * 2:
        #     print("⚠️ 达到最大步数，强制结束")
        #     return {"next": "Final_Answer"}
        
        response = llm.invoke([SystemMessage(content=prompt)])
        decision = response.content.strip().split("\n")[0].strip()
        # if len(state["messages"]) > MAX_STEPS:
            
        #     return {"next": "Final_Answer"}
        node_map = {
            "final_answer": "Final_Answer",
            "final": "Final_Answer",
            "结束": "Final_Answer",
            "完成": "Final_Answer"
        }

        next_node = node_map.get(decision.lower(), decision)
        print(f"🔀 Supervisor 决定 → {next_node}")
        return {"next": next_node}


# Cell 5: 专业 Agent

researcher = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SystemMessage(content="你是技术研究员，擅长查找最新最佳实践和技术方案。")
)

coder = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SystemMessage(content="你是资深 Python/C# 开发者，擅长编写高质量、可维护的代码。")
)

reviewer = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SystemMessage(content="你是严格的代码审查专家，专注于代码质量、安全性和可维护性。")
)

print("✅ 三个专业 Agent 创建完成")

# ====================== Nodes ======================
# Cell 6: Reflection（改进版）
reflection_prompt = SystemMessage(content="""你是一个专业的反思节点。
请对当前工作进行总结，并明确判断下一步应该怎么做。

当前历史：{messages}

请按以下格式输出：
总结：...
问题：...
下一步建议：（明确写出应该去哪个节点：Reviewer / Coder / Final_Answer）""")


def reflection_node(state: AgentState):
    with tracer.start_as_current_span("reflection_node"):
        messages = state["messages"][-10:]   # 取更多历史
        prompt = reflection_prompt.content.format(messages=messages)

        response = llm.invoke([SystemMessage(content=prompt)])
        reflection_text = response.content

        print("🤔 Reflection:", reflection_text[:200] + "..." if len(reflection_text) > 200 else reflection_text)

        return {
            "reflections": [reflection_text],
            "messages": [HumanMessage(content=f"[Reflection] {reflection_text}")]
        }


def researcher_node(state: AgentState):
    with tracer.start_as_current_span("researcher_node"):
        messages = state["messages"]
        print(f"researcher_node state {messages[-1]}")
        result = researcher.invoke(state)
        print(f"researcher_node result {messages[-1]}")
        return {"messages": result["messages"]}


def coder_node(state: AgentState):
    with tracer.start_as_current_span("coder_node"):
        messages = state["messages"]
        print(f"coder_node state {messages[-1]}")
        result = coder.invoke(state)
        print(f"coder_node result {messages[-1]}")
        return {"messages": result["messages"]}


def reviewer_node(state: AgentState):
    with tracer.start_as_current_span("reviewer_node"):
        messages = state["messages"]
        print(f"reviewer_node state {messages[-1]}")
        result = reviewer.invoke(state)
        print(f"reviewer_node result {messages[-1]}")
        return {"messages": result["messages"]}


def final_answer_node(state):
    with tracer.start_as_current_span("final_answer_node"):
        final_text = state["messages"][-1].content
        last_ai_message = next((msg for msg in reversed(state["messages"]) if isinstance(msg, AIMessage)), None)
        if last_ai_message:
            final_text = last_ai_message.content
        print(f"final_answer_node state {final_text}")
        if state.get("reflections"):
            final_text += "\n\n【系统反思】\n" + "\n".join(state["reflections"])
        if state.get("human_feedback"):
            final_text += f"\n\n【用户反馈】：{state['human_feedback']}"

        return {"final_answer": final_text, "messages": state["messages"]}
# ====================== Graph ======================



@st.cache_resource
def get_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Coder", coder_node)          # ← ADD THIS
    workflow.add_node("Reviewer", reviewer_node)    # ← ADD THIS
    workflow.add_node("Reflection", reflection_node)
    workflow.add_node("Final_Answer", final_answer_node)

    workflow.add_edge(START, "Supervisor")

    workflow.add_conditional_edges(
        "Supervisor",
        lambda s: s.get("next", "Final_Answer"),
        {
            "Researcher": "Researcher",
            "Final_Answer": "Final_Answer",
            "Coder": "Coder",           # ← 加这行
            "Reviewer": "Reviewer",     # ← 加这行
        }
    )

    workflow.add_edge("Researcher", "Reflection")
    workflow.add_edge("Reflection", "Final_Answer")
    workflow.add_edge("Reflection", "Supervisor") # ← 改成回 Supervisor，而不是直接 Final_Answer
    workflow.add_edge("Final_Answer", END)

    # return workflow.compile(checkpointer=memory)
         # 新版 RedisSaver 提供的方法
    return workflow
    print("get_multiple_agent done")

config = {"configurable": {"thread_id": "dev_agent_thread_001"}}
# with get_multiple_agent() as multi_agent:


# ====================== Streamlit UI ======================
def ui(agent):
    st.title("🤖 DevAgent - Multi-Agent AI 职业助手")
    st.caption("10年开发经验的 AI Engineer | 支持 Reflection + Human-in-the-Loop")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 显示历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("请输入你的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Multi-Agent 系统思考中..."):
                result = agent.invoke({
                    "messages": [HumanMessage(content=prompt)],
                    "reflections": [],
                    "human_feedback": ""
                }, config=config)

                final_answer = result.get("final_answer", result["messages"][-1].content)
                st.markdown(final_answer)

                # 显示反思
                if result.get("reflections"):
                    with st.expander("🤔 系统反思"):
                        for r in result["reflections"]:
                            st.write(r)

        st.session_state.messages.append({"role": "assistant", "content": final_answer})


    # 侧边栏
    with st.sidebar:
        st.header("配置")
        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.rerun()
        st.caption("Day 9 - Streamlit Frontend")


@traceable
def run():
    with RedisSaver.from_conn_string(os.getenv("REDIS_URL")) as cp:
        
        cp.setup()
        workflow = get_workflow()
        multi_agent = workflow.compile(checkpointer=cp)

        ui(multi_agent)
        
    
        # ai_reply = multi_agent.invoke({
        #     "messages": [HumanMessage(content="帮我优化 AI Engineer 岗位的简历")],
        #     "reflections": [],
        #     "human_feedback": ""
        # }, config=config)
        # print(ai_reply.get("final_answer", ai_reply["messages"][-1].content))


        

if __name__ == "__main__":
    run()
     