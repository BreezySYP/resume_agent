"""ragas_eval/evaluator.py — RAGAS 自动评估（新写法）"""
from __future__ import annotations

import datetime
import uuid

from langsmith import Client as LangSmithClient
from loguru import logger

from shared.configs.settings import LANGSMITH_PROJECT
from shared.configs.tracing import get_tracer, span_error

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
    """把评估分数推送到 LangSmith。

    run_id（job_id）只作为关联字段放进 metadata；每次调用使用独立的 LangSmith
    run id，避免同一 job_id 被重复处理时触发服务端 409（Duplicate run update）。
    推送失败只记 warning，不影响业务。
    """
    ls_run_id = str(uuid.uuid4())
    try:
        _ls_client.create_run(
            id=ls_run_id,
            name="ragas_eval",
            run_type="chain",
            project_name=LANGSMITH_PROJECT,
            inputs={"question": question},
            outputs={"answer": answer},
            metadata={"job_id": run_id} if run_id else None,
        )
        _ls_client.update_run(
            ls_run_id,
            end_time=datetime.datetime.utcnow(),
            outputs={
                "answer": answer,
                **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
            },
        )
        for key, value in scores.items():
            if isinstance(value, float):
                _ls_client.create_feedback(
                    run_id=ls_run_id,
                    key=f"ragas_{key}",
                    score=value,
                    comment=f"Auto RAGAS eval @ {scores.get('timestamp', '')}",
                )
    except Exception as e:
        logger.warning("push_to_langsmith failed (job_id={}): {}", run_id, e)


if __name__ == "__main__":
    from shared.models.deepseek import get_deepseek
    print(uuid.uuid4())
    run_simple_ragas("今天天气怎么样", ["晴天暖和","阴天凉快", "今天是2026-07-29", "夏季天气炎热", "2026-07-28日新闻，预计明天晴天"], "今天预计晴天，天气炎热", get_deepseek(), "f7ccbd38-414d-472e-a786-a859eb22d6c7")
