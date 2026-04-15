from pydantic import BaseModel, Field
from typing import List, Optional, Any


# ---- Request ----
class QueryRequest(BaseModel):
    query: str = Field(..., description="User query")


# ---- Response ----
class QueryResponse(BaseModel):
    query: str
    answer: str
    retrieved_results: List[dict]

    # ✅ NEW (optional for SQL)
    sql_query: Optional[str] = None
    sql_result: Optional[Any] = None