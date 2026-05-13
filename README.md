uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0

uv run streamlit run src/main.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false

uv run python -m rag.ingest data/resumes/Sun_Yapeng_Developer_2026_en.pdf docs/jd.md


uv pip freeze

docker exec devagent-ollama ollama pull qwen2.5:14b
docker exec devagent-ollama ollama pull nomic-embed-text