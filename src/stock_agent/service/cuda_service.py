"""service/cuda_service.py — 调用宿主机 rerank 服务"""
import pandas as pd
import requests
from shared.configs.settings import CUDA_RERANK_URL


def rerank(query: str, docs: list[str], timeout: int = 30) -> pd.DataFrame:
    resp = requests.post(
        CUDA_RERANK_URL, 
        json={"query": query, 
              "docs": docs},
        timeout=timeout)
    resp.raise_for_status()
    scores = resp.json()["scores"]
    result = pd.DataFrame(zip(scores, docs))
    result.columns = ["rerank_score", "docs"]
    return result


if __name__ == "__main__":
    print(rerank("液冷数据中心", ["冬天夜里武汉中心很冷", "数据中心"]))
