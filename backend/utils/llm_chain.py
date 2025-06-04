import openai
import os
from backend.utils.params import SCHOOL_PARAMS, PARAM_VARIANTS
from typing import List, Dict

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "OPENAI_API_KEY не найден в окружении!"

# Формируем prompt для LLM

def build_prompt(passages: List[str], question: str) -> str:
    """
    Собирает prompt для LLM: сначала инструкции, затем фрагменты, затем вопрос.
    """
    params_str = ', '.join(SCHOOL_PARAMS)
    prompt = f"""
Ты — эксперт по анализу школьной документации. Извлеки значения следующих параметров (ключи на русском, значения — как в тексте):
{params_str}

Используй только предоставленные фрагменты документа (в формате Markdown):

"""
    for i, passage in enumerate(passages):
        prompt += f"Фрагмент {i+1}:
{passage}
\n"
    prompt += f"\nВопрос: {question}\n\nОтвет верни в виде JSON, где ключи — параметры, а значения — строки или null. Не придумывай значения, если их нет в тексте."
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
    return response.choices[0].message.content

# Постобработка: привести ключи к SCHOOL_PARAMS, учесть варианты

def normalize_answer(llm_json: Dict[str, str]) -> Dict[str, str]:
    """
    Приводит ключи к SCHOOL_PARAMS, учитывая русские варианты.
    """
    result = {k: None for k in SCHOOL_PARAMS}
    for key, value in llm_json.items():
        for param, variants in PARAM_VARIANTS.items():
            if key.lower() in [v.lower() for v in variants] or key.lower() == param.lower():
                result[param] = value
    return result 