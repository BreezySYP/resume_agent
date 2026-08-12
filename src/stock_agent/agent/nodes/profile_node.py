import datetime
import json
from typing import Any, Dict, List, Literal
from zoneinfo import ZoneInfo

import pandas as pd
from agent.tools import search_stock_profile, tav_search
from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from event.decorator import node
from service.cuda_service import rerank
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek
from shared.text.stock_text import build_stock_profile_text
from shared.metrics.prome import invoke_with_metrics

from pydantic import BaseModel, Field
from loguru import logger

MAX_ITER = 3


class SearchPlan(BaseModel):
    finished: bool = Field(description="是否已经覆盖行业，可以结束搜索")
    keywords: list[str] = Field(description="下一轮搜索关键词")
    reason: str = Field(description="为什么生成这些关键词")

@node(node_name="profile", title="股票档案节点")
def profile_node(state: AgentState):

    # 第一轮关键词
    first_prompt = HumanMessage(content=f"""
        用户问题：
        {state["user_question"]}

        不要回答问题。
        请提取3~5个搜索关键词。

        例如：
        芯片 -> 芯片、半导体、集成电路
        机器人 -> 机器人、工业机器人、人形机器人

        仅返回JSON：
        {{
            "keywords":[]
        }}
    """)

    model_name = "deepseek-chat"
    model = get_deepseek(model=model_name)
    parser = JsonOutputParser(pydantic_object=SearchPlan)
    keywords = model.invoke([first_prompt]).content
    keywords = json.loads(keywords)["keywords"]
    searched_keywords = set()
    all_profiles = {}

    for i in range(MAX_ITER):
        logger.debug("start {} iter for profile node", i)
        current_result = []

        # ---------- 搜索 ----------
        for kw in keywords:
            if kw in searched_keywords:
                continue
            searched_keywords.add(kw)
            docs = search_stock_profile.invoke({"query": kw, "topk": 20})
            if not docs:
                continue
            if isinstance(docs, dict):
                docs = [docs]
            current_result.extend(docs)

        # ---------- 去重 ----------
        for stock in current_result:
            all_profiles[stock["code"]] = stock

        companies = "\n".join(
            f'{x["code"]} {x["name"]}'
            for x in all_profiles.values()
        )

        business = "\n".join(
            x.get("business", "")
            for x in all_profiles.values()
        )
        SEARCH_PROMPT = """
            你是一名A股行业研究员。

            用户问题：
            {question}

            已经搜索过的关键词：
            {searched_keywords}

            目前已经召回的股票：
            {companies}

            经营范围摘要：
            {business}

            你的任务：
            1. 判断目前行业覆盖是否完整
            2. 如果不完整，请生成下一轮搜索关键词
            3. 不要重复已经搜索过的关键词
            4. 尽量覆盖整个产业链（上游、中游、下游）
            5. 每轮最多生成5个关键词

            返回JSON：
            {format_instructions}
            """
        # ---------- Reflection ----------
        prompt = HumanMessage(content=SEARCH_PROMPT.format(
            question=state["user_question"],
            searched_keywords=list(searched_keywords),
            companies=companies,
            business=business,
            format_instructions=parser.get_format_instructions()
        ))

        response = model.invoke([prompt])
        response = invoke_with_metrics(model, [prompt], "stock_profile", model_name)

        plan = parser.parse(response.content)
        if plan["finished"]:
            break
        keywords = plan["keywords"]

    profiles = pd.DataFrame(list(all_profiles.values()))
    scores = rerank(query=state["user_question"], docs=[build_stock_profile_text(row) for _, row in profiles.iterrows()])
    profiles["rerank_score"] = scores["rerank_score"]
    profiles = profiles.loc[profiles["rerank_score"].nlargest(20).index]
    profiles = profiles.drop(columns=["scope"])
    profiles = profiles.to_dict(orient="records")
    # logger.debug("finish profile node")

    # generate_golden_standard_with_llm(state["user_question"])
  
    return {
        "stock_profile": profiles,
        "rag_contexts": [profiles]
    }

if __name__ == "__main__":
    
    state = AgentState()
    state["user_question"] = "国内AI应用前景如何，有什么投资建议，最好能帮我发现下半年最有可能暴增的冷门潜力股，而不是给我大家都知道的龙头股？"
    state["job_id"] = "profile_job"
    state["thread_id"] = "profile_thread"
    # print(profile_node(state).get("stock_profile"))

    # golden_standard = generate_golden_standard_from_candidates(
    #     state["user_question"]
    # )

    # golden_eval = DynamicGoldenStandard()
    # golden = golden_eval.get_golden_standard(state["user_question"])
    # print(golden)