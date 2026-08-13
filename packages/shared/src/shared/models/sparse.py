# packages/shared/models/sparse.py
from functools import lru_cache
from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector


@lru_cache(maxsize=1)
def get_sparse_model():
    return SparseTextEmbedding("Qdrant/bm25")


def embed_sparse(text: str) -> SparseVector:
    emb = next(iter(get_sparse_model().embed(text)))
    return SparseVector(
        indices=emb.indices.tolist(),
        values=emb.values.tolist(),
    )