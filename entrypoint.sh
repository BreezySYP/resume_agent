#!/bin/bash
set -e

echo "🚀 Starting DevAgent Production..."

# # 检查 Chroma 数据库
# echo "📊 Checking vector database..."
# if [ ! -d "data/chroma_db" ]; then
#     echo "⚠️  Chroma DB not found, will be created on first run"
# fi

echo "✅ Starting Streamlit..."
exec streamlit run ./src/main.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false