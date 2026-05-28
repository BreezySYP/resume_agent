uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0

uv run streamlit run src/main.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false

uv run python -m stock_agent.rag.ingest data/resumes/Sun_Yapeng_Developer_2026_en.pdf docs/jd.md


uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload


# 先把基础设施和两个服务都跑起来
docker-compose up -d redis mysql minio
docker-compose up -d dev-agent stock-agent



# 确认两个服务都健康
curl http://localhost:8003/health
curl http://localhost:8004/health

# 确认能互相访问（在 dev-agent 容器里 ping stock-agent）
docker exec -it <dev-agent容器> curl http://stock-agent:8004/health

uv run --project src/stock_agent python -c "
import sys
print('=== sys.path 前10条 ===')
for p in sys.path[:12]:
    print('  ', p)
print('\n=== Import Test ===')
import shared
print('✅ shared 成功:', shared.__file__)
from shared.models.ollama import get_llm
print('✅ get_llm 成功')
"


cd /workspace/src/stock_agent
# 先改 server.py 里所有 from stock_agent.xxx 改成 from xxx
# 然后
uv run langgraph dev --host 0.0.0.0 --port 8002