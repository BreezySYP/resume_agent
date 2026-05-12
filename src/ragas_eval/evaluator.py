"""
ragas/evaluator.py

每次 Final_Answer 后自动调用，评估本轮对话的 RAG 质量。
- 指标：faithfulness + answer_relevancy（不需要 ground_truth）
- 结果：写入 LangSmith + 返回 dict 供 Streamlit 展示
"""
from __future__ import annotations

import datetime
from typing import Any

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langsmith import Client as LangSmithClient

from src.configs.settings import LANGSMITH_PROJECT
from src.configs.tracing import tracer

# LangSmith 客户端（LANGCHAIN_API_KEY 在 .env 里）
_ls_client = LangSmithClient()

METRICS = [faithfulness, answer_relevancy]


def run_ragas(
    question: str,
    contexts: list[str],
    answer: str,
    llm,           # ChatOllama 实例，传入避免循环 import
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    执行 RAGAS 评估，返回结果字典。

    Args:
        question:  用户原始问题
        contexts:  Researcher 检索到的上下文列表
        answer:    Final Answer 文本
        llm:       用于 RAGAS 内部评估的 LLM
        run_id:    LangSmith run_id，用于关联 trace

    Returns:
        {
            "faithfulness": 0.87,
            "answer_relevancy": 0.91,
            "timestamp": "2026-05-10 12:34:56",
            "question": "...",
        }
    """
    with tracer.start_as_current_span("ragas_eval"):
        if not contexts:
            contexts = ["no context retrieved"]

        dataset = Dataset.from_list([
            {
                "question":  question,
                "contexts":  contexts,
                "answer":    answer,
            }
        ])

        try:
            result = evaluate(
                dataset=dataset,
                metrics=METRICS,
                llm=llm,
            )
            scores = {
                "faithfulness":      round(float(result["faithfulness"]),      4),
                "answer_relevancy":  round(float(result["answer_relevancy"]),  4),
                "timestamp":         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "question":          question[:80] + ("..." if len(question) > 80 else ""),
            }
        except Exception as e:
            print(f"⚠️  RAGAS 评估失败: {e}")
            scores = {
                "faithfulness":      None,
                "answer_relevancy":  None,
                "timestamp":         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "question":          question[:80],
                "error":             str(e),
            }

        # ── 上报到 LangSmith ──────────────────────────────────────────────
        _push_to_langsmith(scores, question, answer, run_id)

        print(f"📊 RAGAS → faithfulness={scores['faithfulness']}  "
              f"answer_relevancy={scores['answer_relevancy']}")
        return scores


def _push_to_langsmith(
    scores: dict,
    question: str,
    answer: str,
    run_id: str | None,
) -> None:
    """把评估分数作为 feedback 写入 LangSmith。"""
    try:
        # 如果没有 run_id，创建一个独立的 evaluation run
        if run_id is None:
            run = _ls_client.create_run(
                name="ragas_eval",
                run_type="chain",
                project_name=LANGSMITH_PROJECT,
                inputs={"question": question},
                outputs={"answer": answer},
            )
            run_id = str(run.id)
            _ls_client.update_run(run_id, end_time=datetime.datetime.utcnow())

        for key, value in scores.items():
            if isinstance(value, float):
                _ls_client.create_feedback(
                    run_id=run_id,
                    key=f"ragas_{key}",
                    score=value,
                    comment=f"Auto RAGAS eval @ {scores['timestamp']}",
                )
    except Exception as e:
        print(f"⚠️  LangSmith 上报失败（不影响主流程）: {e}")
