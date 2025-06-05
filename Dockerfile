# Используем официальный Python 3.11 slim
FROM python:3.11-slim

# Устанавливаем системные зависимости для numpy, faiss и других
RUN apt-get update && \
    apt-get install -y build-essential wget git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем tesseract для OCR (если нужен markitdown)
RUN apt-get update && apt-get install -y tesseract-ocr && apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
WORKDIR /app
COPY requirements.txt .

# Используем быстрое зеркало PyPI
RUN pip install -r requirements.txt

COPY . .

# Открываем порты для backend и frontend
EXPOSE 8000 8501

# По умолчанию запускаем bash (или можно CMD ["uvicorn", ...])
CMD ["bash"] 