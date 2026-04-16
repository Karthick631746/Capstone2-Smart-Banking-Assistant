from src.api.v1.tools.vector_search import similarity_search
from src.api.v1.tools.fts_search import fts_search


def hybrid_search(query: str):

    vector_results = similarity_search(query, k=10)
    fts_results = fts_search(query)

    rrf_scores = {}
    chunk_map = {}

    # Vector
    for rank, doc in enumerate(vector_results):
        key = str(doc["id"])
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (60 + rank + 1)
        chunk_map[key] = doc

    # FTS
    for rank, doc in enumerate(fts_results):
        key = str(doc["id"])
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (60 + rank + 1)
        chunk_map[key] = doc

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    return [chunk_map[k] for k, _ in ranked[:5]]
