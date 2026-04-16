import os
import numpy as np

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.core.db import fetch_chunks

# ✅ Embedding model
_embeddings_model = GoogleGenerativeAIEmbeddings(
    model=os.getenv("GOOGLE_EMBEDDING_MODEL"),
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    output_dimensionality=1536,
)


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def similarity_search(query: str, k: int = 5, chunk_type: str | None = None) -> list[dict]:

    # 🔥 1. Embed query
    query_vec = _embeddings_model.embed_query(query)

    # 🔥 2. Fetch chunks from DB
    chunks = fetch_chunks(limit=50, chunk_type=chunk_type)

    # 🔥 3. Compute similarity
    for chunk in chunks:
        emb = chunk.get("embedding")

        # Convert string → list
        if isinstance(emb, str):
            emb = [float(x) for x in emb.strip("[]").split(",")]

        chunk["similarity"] = cosine_similarity(query_vec, emb)

    # 🔥 4. Sort
    chunks = sorted(chunks, key=lambda x: x["similarity"], reverse=True)

    # 🔥 5. Return top-k
    return chunks[:k]
