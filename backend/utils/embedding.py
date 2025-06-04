import tiktoken
import openai
import os
from typing import List, Tuple
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем ключ из окружения
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "OPENAI_API_KEY не найден в окружении!"

# Чанкинг Markdown на куски ≤800 токенов с overlap

def chunk_markdown(md_text: str, max_tokens: int = 800, overlap: int = 100) -> List[str]:
    """
    Делит текст на чанки по max_tokens с overlap.
    """
    enc = tiktoken.encoding_for_model("text-embedding-3-large")
    tokens = enc.encode(md_text)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i+max_tokens]
        chunk = enc.decode(chunk_tokens)
        chunks.append(chunk)
        if i + max_tokens >= len(tokens):
            break
        i += max_tokens - overlap
    return chunks

# Получение эмбеддингов через OpenAI

def get_embeddings(chunks: List[str]) -> List[List[float]]:
    """
    Получает эмбеддинги для каждого чанка через OpenAI API.
    """
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    embeddings = []
    for chunk in chunks:
        resp = client.embeddings.create(
            input=chunk,
            model="text-embedding-3-large"
        )
        embeddings.append(resp.data[0].embedding)
    return embeddings 