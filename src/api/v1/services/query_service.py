
from src.api.v1.agents.agent import run_agent


def query_documents(query: str) -> dict:

    agent_output = run_agent(query)

    response = agent_output.get("response", {})
    answer = response.get("answer", "")

    # 🔥 Detect if SQL was used
    is_sql = "sql_query" in response

    retrieved_results = []

    # ─────────────────────────────
    # ✅ RAG FLOW
    # ─────────────────────────────
    if not is_sql:
        chunks = agent_output.get("reranked_docs", [])

        for c in chunks:
            item = {
                "chunk_id": c.get("id"),
                "content": c.get("content"),
                "chunk_type": c.get("chunk_type"),
                "page": c.get("page_number"),
                "section": c.get("section"),
                "source": c.get("source_file"),
                "similarity": round(c.get("similarity", 0), 4),
                "created_date": str(c.get("created_date")),
            }

            if c.get("chunk_type") == "image":
                item["image_path"] = c.get("image_path")

            retrieved_results.append(item)

        return {
            "query": query,
            "answer": answer,
            "retrieved_results": retrieved_results
        }

    # ─────────────────────────────
    # ✅ SQL FLOW
    # ─────────────────────────────
    else:
        return {
            "query": query,
            "answer": answer,
            "retrieved_results": [],  # no chunks for SQL
            "sql_query": response.get("sql_query"),
            "sql_result": response.get("sql_result")
        }