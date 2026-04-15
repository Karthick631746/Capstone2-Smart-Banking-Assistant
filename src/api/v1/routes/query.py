from fastapi import APIRouter
from src.api.v1.schemas.query_schema import QueryRequest, QueryResponse
from src.api.v1.services.query_service import query_documents

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    print(f"Received query: {request.query}")
    result = query_documents(request.query)  # Issue 17
    return QueryResponse(**result)

