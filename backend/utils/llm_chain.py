import openai
import os
from typing import List

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "OPENAI_API_KEY не найден в окружении!"

# Формируем prompt для LLM

def build_prompt(passages: List[str], question: str) -> str:
    """Формирует prompt: перечисляет фрагменты и задаёт вопрос. Без жёстких инструкций по параметрам."""
    prompt = "Ты — помощник, который отвечает на вопросы по документу. Используй только предоставленные фрагменты Markdown.\n\n"
    for i, passage in enumerate(passages):
        # Добавляем очередной фрагмент документа в prompt (KISS)
        prompt += f"""Фрагмент {i+1}:
{passage}
\n"""
    prompt += f"\nВопрос: {question}\n\nОтветь кратко и по существу на русском языке."
    return prompt

# Вызов LLM (GPT-4o)

def ask_llm(prompt: str) -> str:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=512
    )
    # Гарантируем возврат строки, даже если content == None (KISS)
    return response.choices[0].message.content or ""

# Постобработка: привести ключи к SCHOOL_PARAMS, учесть варианты

def normalize_answer(obj):
    return obj

# Для совместимости оставляем заглушку normalize_answer, возвращающую исходную строку или объект 