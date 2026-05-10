uv run jupyter lab --allow-root --no-browser --ip=0.0.0.0

uv run streamlit run main.py

python -m rag.ingest data/resumes/Sun_Yapeng_Developer_2026_en.pdf.pdf docs/jd.md


uv pip freeze