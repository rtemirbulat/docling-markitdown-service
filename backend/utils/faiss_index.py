import faiss
import numpy as np
import os
import json
from typing import List, Tuple

# Папка для индексов
INDEX_DIR = os.path.join("data", "index")

# Получить путь к индексу по pipeline

def get_index_path(file_id: str, pipeline: str) -> str:
    return os.path.join(INDEX_DIR, f"{file_id}_{pipeline}.faiss")

def get_meta_path(file_id: str, pipeline: str) -> str:
    return os.path.join(INDEX_DIR, f"{file_id}_{pipeline}.json")

# Создать и сохранить индекс

def create_faiss_index(embeddings: List[List[float]], passages: List[str], file_id: str, pipeline: str):
    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    arr = np.array(embeddings).astype('float32')
    index.add(arr)
    faiss.write_index(index, get_index_path(file_id, pipeline))
    # Сохраняем соответствие: passage_id -> текст
    with open(get_meta_path(file_id, pipeline), "w", encoding="utf-8") as f:
        json.dump(passages, f, ensure_ascii=False)

# Загрузить индекс и метаинформацию

def load_faiss_index(file_id: str, pipeline: str):
    index = faiss.read_index(get_index_path(file_id, pipeline))
    with open(get_meta_path(file_id, pipeline), "r", encoding="utf-8") as f:
        passages = json.load(f)
    return index, passages

# Поиск top_k ближайших чанков

def search_faiss_index(file_id: str, pipeline: str, query_emb: List[float], top_k: int = 5) -> Tuple[List[Tuple[int, float]], list]:
    index, passages = load_faiss_index(file_id, pipeline)
    arr = np.array([query_emb]).astype('float32')
    D, I = index.search(arr, top_k)
    # Возвращаем индексы и расстояния
    return [(int(i), float(d)) for i, d in zip(I[0], D[0])], passages 