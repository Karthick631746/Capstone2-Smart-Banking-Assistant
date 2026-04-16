import json
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

_conn = os.getenv("PG_CONNECTION_STRING", "").replace("postgresql+psycopg", "postgresql")


def fts_search(query: str):

    sql = """
        SELECT
            mc.id,
            mc.content,
            mc.chunk_type,
            mc.page_number,
            mc.section,
            mc.source_file,
            mc.image_path,
            d.ingested_at AS created_date,

            ts_rank(
                to_tsvector('english', mc.content),
                websearch_to_tsquery('english', %(query)s)
            ) AS score

        FROM multimodal_chunks mc
        LEFT JOIN documents d ON mc.doc_id = d.id

        WHERE to_tsvector('english', mc.content)
              @@ websearch_to_tsquery('english', %(query)s)

        ORDER BY score DESC
        LIMIT 5;
    """

    with psycopg.connect(_conn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"query": query})
            rows = cur.fetchall()

    results = []
    for row in rows:
        row = dict(row)
        row["similarity"] = float(row["score"])
        results.append(row)

    return results
