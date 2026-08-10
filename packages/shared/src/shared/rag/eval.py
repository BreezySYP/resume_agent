"""ragas_eval/evaluator.py — RAGAS 自动评估（新写法）"""
from __future__ import annotations
import datetime
from typing import Any
import uuid
from datasets import Dataset
from loguru import logger
from langsmith import Client as LangSmithClient
from shared.configs.settings import LANGSMITH_PROJECT
from shared.configs.tracing import get_tracer, span_error
import numpy as np

_ls_client = LangSmithClient()


_tracer = get_tracer("agent.ragas")

def run_ragas(question: str, answer: str, run_id: uuid, scores: dict) -> dict:
    with _tracer.start_as_current_span("agent.ragas", attributes={"question": question, "answer": answer}) as span:
        """轻量版 faithfulness + relevancy 评估"""

        # 1. Faithfulness：答案是否被 context 支持
        faith_prompt = f"""请判断下面的回答是否完全基于给定的上下文，没有编造信息。
            只输出 0 到 1 的分数（1 表示完全忠实，0 表示严重幻觉）。

            上下文：
            {context_text}

            回答：
            {answer}

            分数："""

                # 2. Answer Relevancy：回答是否切题
        rel_prompt = f"""请判断下面的回答与问题的相关程度。
            只输出 0 到 1 的分数（1 表示非常相关）。

            问题：{question}
            回答：{answer}

            分数："""

        try:
            faith_score = float(llm.invoke(faith_prompt).content.strip()[:4])
            rel_score = float(llm.invoke(rel_prompt).content.strip()[:4])
        except Exception as e:
            faith_score, rel_score = None, None
            span_error(span, e)

        scores = {
            "faithfulness": faith_score,
            "answer_relevancy": rel_score,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": question[:80],
        }
        push_to_langsmith(scores, question, answer, run_id)
        return scores


def push_to_langsmith(scores: dict, question: str, answer: str, run_id: str) -> None:
    _ls_client.create_run(id=run_id,
        name="ragas_eval", run_type="chain", project_name=LANGSMITH_PROJECT,
        inputs={"question": question}, outputs={"answer": answer},
    )
    _ls_client.update_run(
        run_id,
        end_time=datetime.datetime.utcnow(),
        outputs={
            "answer": answer,
            **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
        },
        # 可选：明确标记成功
        # error=None,
    )
    for key, value in scores.items():
        if isinstance(value, float):
            _ls_client.create_feedback(run_id=run_id, key=f"ragas_{key}", score=value,
                                        comment=f"Auto RAGAS eval @ {scores['timestamp']}")


if __name__ == "__main__":
    from shared.models.deepseek import get_deepseek
    print(uuid.uuid4())
    run_simple_ragas("今天天气怎么样", ["晴天暖和","阴天凉快", "今天是2026-07-29", "夏季天气炎热", "2026-07-28日新闻，预计明天晴天"], "今天预计晴天，天气炎热", get_deepseek(), "f7ccbd38-414d-472e-a786-a859eb22d6c7")