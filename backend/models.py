from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict

# Параметры школы (ключи на русском)
SCHOOL_PARAMS = [
    "Школа", "ТИП", "ПОДТИП", "КОЛИЧЕСТВО УЧЕНИКОВ", "КВАДРАТУРА", "ЭТАЖНОСТЬ",
    "ПЛОЩАДЬ ЗЕМЛИ", "НАЛИЧИЕ ДЕМОНТАЖНЫХ РАБОТ", "ФИТНЕСС-ЗАЛ", "РЕЗЕРВУАРЫ",
    "КОТЕЛЬНАЯ", "НАРУЖНЫЙ СТАДИОН", "КОЛИЧЕСТВО СПОРТЗАЛОВ", "МАЛЫЙ СПОРТЗАЛ",
    "БОЛЬШОЙ СПОРТЗАЛ", "РЕГИОН"
]

class UploadResponse(BaseModel):
    job_id: str = Field(..., description="ID фоновой задачи")

class JobStatusResponse(BaseModel):
    status: Literal["pending", "converting", "embedding", "ready", "error"]
    progress: float = Field(..., description="Прогресс выполнения (0-1)")
    detail: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    pipeline: Literal["docling", "markitdown"]

class QueryResult(BaseModel):
    answer: Dict[str, str]  # Ключи — параметры школы
    passages: List[str]     # Markdown-фрагменты, использованные для ответа 