# DocLing-Markitdown Service

Сервис для конвертации документов (PDF, DOCX, XLSX и др.) в Markdown с помощью DocLing и Markitdown, индексации эмбеддингов и извлечения параметров школьных объектов через LLM.

Начиная с версии X.Y поддерживается прямая загрузка Markdown-файлов. Такой файл минует стадию конвертации и сразу разбивается на фрагменты, преобразуется в эмбеддинги и индексируется. Это позволяет повторно уточнять и обогащать Markdown-документ вручную и загружать обновлённую версию без лишних преобразований.

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
