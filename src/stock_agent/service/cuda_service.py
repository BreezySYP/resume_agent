import requests
import os
import pandas as pd

rerank_url = os.getenv("CUDA_RERANK_URL", "http://host.docker.internal:8000/api/v1/rerank")
def rerank(query, docs: list):
    resp = requests.post(
        rerank_url,
        json={
            "query": query,
            "docs": docs
        }
    )

    scores = resp.json()["scores"]
    result = pd.DataFrame(zip(scores, docs)) 
    result.columns = ["rerank_score", "docs"]
    return result

# def ping():
#     """从 Docker 容器内调用宿主机服务"""
    
#     # 多个候选地址，增加容错
#     urls = [
#         "http://host.docker.internal:8000/api/v1/ping",
#         "http://172.17.0.1:8000/api/v1/ping",
#         "http://host.docker.internal:8000/api/v1/ping/",
#     ]
    
#     for url in urls:
#         try:
#             resp = requests.get(url, timeout=10)
#             if resp.status_code == 200:
#                 print(f"✅ 成功访问: {url}")
#                 return resp.text
#             else:
#                 print(f"⚠️  状态码异常 {resp.status_code}: {url}")
#         except Exception as e:
#             print(f"❌ 连接失败 {url}: {e}")
    
#     return "❌ 无法连接宿主机服务"

if __name__ == "__main__":
    # print(ping())
    scores = rerank("液冷数据中心", ["冬天夜里武汉中心很冷","数据中心"])
    print(scores)