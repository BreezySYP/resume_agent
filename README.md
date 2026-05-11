uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0

uv run streamlit run main.py

uv run python -m rag.ingest data/resumes/Sun_Yapeng_Developer_2026_en.pdf docs/jd.md


uv pip freeze