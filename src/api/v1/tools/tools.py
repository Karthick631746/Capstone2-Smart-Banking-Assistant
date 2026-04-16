from src.api.v1.tools.vector_search import similarity_search
from src.api.v1.tools.fts_search import fts_search
from src.api.v1.tools.hybrid_search import hybrid_search


def vector_search_tool(query: str):
    return similarity_search(query, k=10)


def fts_search_tool(query: str):
    return fts_search(query)


def hybrid_search_tool(query: str):
    return hybrid_search(query)


TOOLS = {
    "vector_search": vector_search_tool,
    "fts_search": fts_search_tool,
    "hybrid_search": hybrid_search_tool
}
