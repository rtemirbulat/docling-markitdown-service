import os
import tempfile
import subprocess
from typing import Literal

# Исключения для обработки ошибок
class ConversionError(Exception):
    pass

# Конвертация через DocLing

def convert_with_docling(input_path: str, output_path: str) -> bool:
    """
    Конвертирует файл в Markdown с помощью DocLing CLI.
    Возвращает True при успехе.
    """
    try:
        # DocLing поддерживает команду: docling convert input -o output.md
        result = subprocess.run([
            "docling", "convert", input_path, "-o", output_path
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"[DocLing] Ошибка: {e}")
        return False

# Конвертация через Markitdown

def convert_with_markitdown(input_path: str, output_path: str) -> bool:
    """
    Конвертирует файл в Markdown с помощью Markitdown CLI.
    Возвращает True при успехе.
    """
    try:
        # Markitdown поддерживает команду: markitdown input -o output.md
        result = subprocess.run([
            "markitdown", input_path, "-o", output_path
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"[Markitdown] Ошибка: {e}")
        return False

# Универсальный конвертер с fallback

def convert_to_markdown(input_path: str, output_path: str, pipeline: Literal["docling", "markitdown"]) -> str:
    """
    Конвертирует файл в Markdown выбранным pipeline.
    Если выбран markitdown и он не сработал — fallback на docling.
    Возвращает имя pipeline, который реально сработал.
    """
    if pipeline == "markitdown":
        ok = convert_with_markitdown(input_path, output_path)
        if ok:
            return "markitdown"
        print("[Conversion] Markitdown не сработал, fallback на DocLing...")
        ok = convert_with_docling(input_path, output_path)
        if ok:
            return "docling"
        raise RuntimeError("Не удалось конвертировать файл ни одним pipeline")
    else:
        ok = convert_with_docling(input_path, output_path)
        if ok:
            return "docling"
        print("[Conversion] DocLing не сработал, fallback на Markitdown...")
        ok = convert_with_markitdown(input_path, output_path)
        if ok:
            return "markitdown"
        raise RuntimeError("Не удалось конвертировать файл ни одним pipeline") 