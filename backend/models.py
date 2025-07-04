from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class UploadResponse(BaseModel):
    job_id: str = Field(..., description="ID фоновой задачи")

class JobStatusResponse(BaseModel):
    status: Literal["pending", "converting", "embedding", "ready", "error"]
    progress: float = Field(..., description="Прогресс выполнения (0-1)")
    detail: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    pipeline: Literal["docling", "markitdown", "markdown"]

class QueryResult(BaseModel):
    answer: str            # Текстовый ответ LLM
    passages: List[str]   # Markdown-фрагменты, использованные для ответа 