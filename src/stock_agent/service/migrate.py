import os

import pandas as pd
from shared.models.ollama import get_embedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)

qdrant_url = os.getenv("QDRANT_URL")
client = QdrantClient(url=qdrant_url)
model = get_embedding()


