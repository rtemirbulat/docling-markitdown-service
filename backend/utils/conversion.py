import os
import tempfile
import subprocess
import logging
from typing import Literal
import time

logger = logging.getLogger(__name__)

# Исключения для обработки ошибок
class ConversionError(Exception):
    pass

# Helper: write markdown string to file
def _write_markdown(md_text: str, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_text)

# Конвертация через DocLing

def convert_with_docling(input_path: str, output_path: str) -> bool:
    """
    Преобразует документ в Markdown через библиотеку DocLing. Сначала
    пытается использовать Python-API (`DocumentConverter`), а при неудаче
    откатывается к CLI-команде `docling convert`.
    """
    # 1) Пробуем Python-API
    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        converter = DocumentConverter()
        result = converter.convert(input_path)
        md_str = result.document.export_to_markdown()
        _write_markdown(md_str, output_path)
        return True
    except Exception as e:
        logger.warning("[DocLing] Python API failed: %s", e, exc_info=True)

    # 2) Фолбэк: CLI
    try:
        result = subprocess.run(
            ["docling", "convert", input_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("[DocLing CLI] stderr:\n%s", result.stderr)
        return result.returncode == 0
    except Exception as e:
        logger.warning("[DocLing CLI] Exception: %s", e, exc_info=True)
        return False

# Конвертация через Markitdown

def convert_with_markitdown(input_path: str, output_path: str) -> bool:
    """
    Конвертирует файл в Markdown с помощью MarkItDown. Сначала пытаемся
    Python-API (`MarkItDown`), затем CLI-утилиту.
    """
    # 1) Python-API
    try:
        start = time.time()
        logger.info("[MarkItDown] Converting via Python API: %s -> %s", input_path, output_path)
        from markitdown import MarkItDown  # type: ignore

        md_converter = MarkItDown(enable_plugins=False)
        result = md_converter.convert(input_path)
        md_str = result.text_content
        _write_markdown(md_str, output_path)
        logger.info("[MarkItDown] Python API finished in %.2f sec", time.time() - start)
        return True
    except Exception as e:
        logger.warning("[MarkItDown] Python API failed: %s", e, exc_info=True)

    # 2) CLI fallback
    try:
        logger.info("[MarkItDown CLI] Running markitdown %s -o %s", input_path, output_path)
        result = subprocess.run(
            ["markitdown", input_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("[MarkItDown CLI] stderr:\n%s", result.stderr)
        else:
            logger.info("[MarkItDown CLI] Finished in %.2f sec", result.elapsed.total_seconds() if hasattr(result, "elapsed") else 0)
        return result.returncode == 0
    except Exception as e:
        logger.warning("[MarkItDown CLI] Exception: %s", e, exc_info=True)
        return False

# Универсальный конвертер с fallback

def convert_to_markdown(input_path: str, output_path: str, pipeline: Literal["docling", "markitdown"]) -> str:
    """
    Конвертирует файл в Markdown выбранным pipeline.
    Если выбран markitdown и он не сработал — fallback на docling.
    Возвращает имя pipeline, который реально сработал.
    """
    logger.info("[Conversion] Requested pipeline: %s for %s", pipeline, input_path)
    if pipeline == "markitdown":
        ok = convert_with_markitdown(input_path, output_path)
        if ok:
            return "markitdown"
        logger.warning("[Conversion] Markitdown не сработал, fallback на DocLing...")
        ok = convert_with_docling(input_path, output_path)
        if ok:
            return "docling"
        raise RuntimeError("Не удалось конвертировать файл ни одним pipeline")
    else:
        ok = convert_with_docling(input_path, output_path)
        if ok:
            return "docling"
        logger.warning("[Conversion] DocLing не сработал, fallback на Markitdown...")
        ok = convert_with_markitdown(input_path, output_path)
        if ok:
            return "markitdown"
        raise RuntimeError("Не удалось конвертировать файл ни одним pipeline") 