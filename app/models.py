from pydantic import BaseModel
from typing import Any


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    sql: str
    results: list[dict[str, Any]]
    answer: str
    row_count: int