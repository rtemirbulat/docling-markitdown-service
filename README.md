# DocLing-Markitdown Service

Сервис для конвертации документов (PDF, DOCX, XLSX и др.) в Markdown с помощью DocLing и Markitdown, индексации эмбеддингов и извлечения параметров школьных объектов через LLM.

## Быстрый старт

1. Установите зависимости:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # или .venv\Scripts\activate на Windows
   pip install -r requirements.txt
   ```
2. Запустите backend:
   ```bash
   uvicorn backend.main:app --reload
   ```
3. Запустите frontend:
   ```bash
   streamlit run frontend/app.py
   ```

## Переменные окружения
- `OPENAI_API_KEY` — ваш ключ OpenAI.
