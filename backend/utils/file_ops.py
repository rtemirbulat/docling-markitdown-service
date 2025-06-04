import os
import uuid
import shutil
import zipfile
import tempfile
from typing import List
from zipfile import ZipFile

DATA_ORIGINAL = os.path.join("data", "original")
DATA_MARKDOWN = os.path.join("data", "markdown")
DATA_INDEX = os.path.join("data", "index")

# Генерация уникального идентификатора
def generate_uuid() -> str:
    return str(uuid.uuid4())

# Сохранение файла
def save_file(file_bytes: bytes, ext: str) -> str:
    os.makedirs(DATA_ORIGINAL, exist_ok=True)
    file_id = generate_uuid()
    path = os.path.join(DATA_ORIGINAL, f"{file_id}.{ext}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return file_id, path

# Сохранение markdown
def save_markdown(file_id: str, markdown: str) -> str:
    os.makedirs(DATA_MARKDOWN, exist_ok=True)
    path = os.path.join(DATA_MARKDOWN, f"{file_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return path

# Сохранение индекса
def save_index(file_id: str, index_json: str) -> str:
    os.makedirs(DATA_INDEX, exist_ok=True)
    path = os.path.join(DATA_INDEX, f"{file_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(index_json)
    return path

# Сохраняет файл в data/original с уникальным именем
def save_original_file(file_bytes: bytes, ext: str) -> str:
    """
    Сохраняет файл и возвращает путь (uuid.ext)
    """
    file_id = str(uuid.uuid4())
    path = os.path.join("data", "original", f"{file_id}.{ext}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return file_id, path

# Сохраняет markdown-файл
def save_markdown_file(file_id: str, md_text: str) -> str:
    path = os.path.join("data", "markdown", f"{file_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_text)
    return path

# Проверяет допустимое расширение
def allowed_ext(filename: str) -> bool:
    allowed = {"pdf", "docx", "xlsx", "csv", "txt", "pptx"}
    return filename.lower().split(".")[-1] in allowed

# Извлекает все PDF из ZIP, возвращает список (имя, bytes)
def extract_pdfs_from_zip(zip_bytes: bytes) -> List[tuple]:
    pdfs = []
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "archive.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for name in zip_ref.namelist():
                if name.lower().endswith('.pdf'):
                    with zip_ref.open(name) as pdf_file:
                        pdfs.append((name, pdf_file.read()))
    return pdfs

# Удаление временных файлов/директорий
def cleanup_path(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.isfile(path):
        os.remove(path) 