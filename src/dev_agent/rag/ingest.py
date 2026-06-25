"""rag/ingest.py — 本地文件入库
用法: python -m rag.ingest docs/resume.pdf docs/jd.md
"""
import sys
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.vector_store import get_vector_store

SUPPORTED = {".pdf", ".txt", ".md", ".markdown"}


def ingest_local_files(paths: list[str], chunk_size: int = 800, chunk_overlap: int = 100) -> int:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_docs = []
    for p in paths:
        path   = Path(p)
        suffix = path.suffix.lower()
        if not path.exists():
            print(f"⚠️  不存在: {p}"); continue
        if suffix not in SUPPORTED:
            print(f"⚠️  不支持: {p}"); continue
        loader = (PyPDFLoader(str(path)) if suffix == ".pdf"
                  else TextLoader(str(path), encoding="utf-8") if suffix == ".txt"
                  else UnstructuredMarkdownLoader(str(path)))
        chunks = splitter.split_documents(loader.load())
        for c in chunks:
            c.metadata.update({"source_type": "local_file", "file_name": path.name})
        all_docs.extend(chunks)
        print(f"  📄 {path.name}: {len(chunks)} chunks")
    if not all_docs:
        print("⚠️  没有可写入的文档"); return 0
    get_vector_store().add_documents(all_docs)
    print(f"✅ 写入 {len(all_docs)} chunks")
    return len(all_docs)


if __name__ == "__main__":
    ingest_local_files(sys.argv[1:])
