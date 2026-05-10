"""
rag/ingest.py
本地文件（PDF / txt / md）切块写入 Redis Vector Store。

用法：
    python -m rag.ingest docs/resume.pdf docs/jd.md
    或在代码中：
    from rag.ingest import ingest_local_files
    ingest_local_files(["./docs/resume.pdf"])
"""
import sys
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter

from rag.vector_store import get_vector_store

SUPPORTED = {".pdf", ".txt", ".md", ".markdown"}


def ingest_local_files(
    paths: list[str],
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> int:
    """
    将文件列表切块后写入 Vector Store。
    返回成功写入的 chunk 数量。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    all_docs = []

    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"⚠️  文件不存在，跳过: {p}")
            continue
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED:
            print(f"⚠️  不支持的格式，跳过: {p}")
            continue

        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suffix == ".txt":
            loader = TextLoader(str(path), encoding="utf-8")
        else:  # .md / .markdown
            loader = UnstructuredMarkdownLoader(str(path))

        docs = loader.load()
        chunks = splitter.split_documents(docs)
        for c in chunks:
            c.metadata["source_type"] = "local_file"
            c.metadata["file_name"] = path.name
        all_docs.extend(chunks)
        print(f"  📄 {path.name}: {len(chunks)} chunks")

    if not all_docs:
        print("⚠️  没有可写入的文档")
        return 0

    vs = get_vector_store()
    vs.add_documents(all_docs)
    print(f"✅ 已写入 {len(all_docs)} chunks 到 Vector Store")
    return len(all_docs)


if __name__ == "__main__":
    files = sys.argv[1:]
    if not files:
        print("用法: python -m rag.ingest <file1> [file2] ...")
        sys.exit(1)
    ingest_local_files(files)
