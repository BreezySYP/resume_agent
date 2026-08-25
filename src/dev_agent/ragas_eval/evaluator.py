"""ragas_eval/evaluator.py — RAGAS 自动评估"""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from datasets import Dataset
from langsmith import Client as LangSmithClient
from loguru import logger
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, faithfulness
from shared.configs.settings import LANGSMITH_PROJECT
from shared.configs.tracing import tracer
from shared.models.ollama_models import get_embedding

_ls_client = LangSmithClient()
METRICS = [faithfulness, answer_relevancy]


def run_ragas(question: str, contexts: list[str], answer: str, llm, run_id: str | None = None) -> dict[str, Any]:
    with tracer.start_as_current_span("ragas_eval"):
        if not contexts:
            contexts = ["no context retrieved"]
        dataset = Dataset.from_list([{"question": question, "contexts": contexts, "answer": answer}])
        try:
            result = evaluate(
                dataset=dataset, metrics=METRICS,
                llm=LangchainLLMWrapper(llm),
                embeddings=LangchainEmbeddingsWrapper(get_embedding()),
            )
            scores = {
                "faithfulness":     round(float(result["faithfulness"]),     4),
                "answer_relevancy": round(float(result["answer_relevancy"]), 4),
                "timestamp":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "question":         question[:80] + ("..." if len(question) > 80 else ""),
            }
        except Exception as e:
            logger.info(f"⚠️  RAGAS 评估失败: {e}")
            scores = {"faithfulness": None, "answer_relevancy": None,
                      "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      "question": question[:80], "error": str(e)}
        _push_to_langsmith(scores, question, answer, run_id)
        logger.info(f"📊 RAGAS → faithfulness={scores['faithfulness']} answer_relevancy={scores['answer_relevancy']}")
        return scores


def _push_to_langsmith(scores: dict, question: str, answer: str, run_id: str | None) -> None:
    try:
        ls_run_id = str(uuid.uuid4())
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
                _ls_client.create_feedback(run_id=ls_run_id, key=f"ragas_{key}", score=value,
                                           comment=f"Auto RAGAS eval @ {scores['timestamp']}")
    except Exception as e:
        logger.info(f"⚠️  LangSmith 上报失败: {e}")
