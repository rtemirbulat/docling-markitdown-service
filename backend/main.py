import os
import shutil
import asyncio
import logging
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
from backend.models import UploadResponse, JobStatusResponse, QueryRequest, QueryResult
from backend.utils.file_ops import save_original_file, allowed_ext, extract_pdfs_from_zip, save_markdown_file
from backend.utils.conversion import convert_to_markdown
from backend.utils.embedding import chunk_markdown, get_embeddings
from backend.utils.faiss_index import create_faiss_index, search_faiss_index, load_faiss_index
from backend.utils.llm_chain import build_prompt, ask_llm
import uuid
from typing import Dict, List
import tempfile
import zipfile

app = FastAPI()

# Хранилище статусов задач (in-memory)
jobs: Dict[str, Dict] = {}

# ---------- Logging config ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- Helper to update job progress/detail ----------
def _update_job(job_id: str, *, progress: float | None = None, detail: str | None = None):
    if progress is not None:
        jobs[job_id]["progress"] = progress
    if detail is not None:
        jobs[job_id]["detail"] = detail
    logger.debug("[job %s] progress=%.2f detail=%s", job_id, jobs[job_id]["progress"], jobs[job_id].get("detail"))

# ---------- Utils ----------

def _zip_markdown(file_ids: List[str], project: str) -> str:
    """Create a temporary zip archive with all markdown files for given file_ids and return path."""
    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tmp_dir, f"{project or 'project'}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in file_ids:
            md_path = os.path.join("data", "markdown", f"{fid}.md")
            if os.path.exists(md_path):
                # add with nicer name inside zip: <project>_<index>.md or original fid
                arcname = os.path.basename(md_path)
                zf.write(md_path, arcname=arcname)
    return zip_path

@app.post("/upload-file", response_model=UploadResponse)
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), pipeline: str = Form("docling"), project: str = Form("default")):
    # Проверяем расширение
    ext = file.filename.split(".")[-1].lower()
    if not allowed_ext(file.filename):
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")
    logger.info("[upload_file] Received file '%s' (pipeline=%s)", file.filename, pipeline)
    file_bytes = await file.read()
    file_id, orig_path = save_original_file(file_bytes, ext)
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0.0, "detail": None, "file_id": file_id, "file_ids": [file_id], "pipeline": pipeline, "project": project}
    logger.debug("[upload_file] Saved original file to %s (file_id=%s, job_id=%s)", orig_path, file_id, job_id)
    background_tasks.add_task(process_file_job, job_id, orig_path, file_id, pipeline)
    return UploadResponse(job_id=job_id)

@app.post("/upload-zip", response_model=UploadResponse)
async def upload_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...), pipeline: str = Form("docling"), project: str = Form("default")):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается ZIP-файл")
    logger.info("[upload_zip] Received zip '%s' (pipeline=%s)", file.filename, pipeline)
    zip_bytes = await file.read()
    pdfs = extract_pdfs_from_zip(zip_bytes)
    logger.debug("[upload_zip] Extracted %d pdf(s) from zip", len(pdfs))
    if not pdfs:
        raise HTTPException(status_code=400, detail="В ZIP нет PDF-файлов")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0.0, "detail": None, "zip": True, "count": len(pdfs), "done": 0, "file_ids": [], "pipeline": pipeline, "project": project}
    background_tasks.add_task(process_zip_job, job_id, pdfs, pipeline)
    return UploadResponse(job_id=job_id)

@app.get("/job-status/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return JobStatusResponse(status=job["status"], progress=job["progress"], detail=job.get("detail"))

@app.post("/query", response_model=QueryResult)
async def query(request: QueryRequest):
    # Для простоты: ищем по последнему загруженному файлу (или расширить под конкретный id)
    file_id = None
    pipeline_used = request.pipeline
    for job in reversed(list(jobs.values())):
        if job.get("file_id"):
            if job["pipeline"] == request.pipeline:
                file_id = job["file_id"]
                pipeline_used = job["pipeline"]
                break
            # Fallback: если точно совпадения по pipeline нет, запоминаем первый попавшийся готовый файл
            if file_id is None:
                file_id = job["file_id"]
                pipeline_used = job["pipeline"]
    if not file_id:
        raise HTTPException(status_code=404, detail="Нет обработанных файлов")
    # Загружаем индекс и markdown-фрагменты (используем подтверждённый pipeline_used)
    index, passages = load_faiss_index(file_id, pipeline_used)
    # Получаем эмбеддинг вопроса
    query_emb = get_embeddings([request.question])[0]
    # Поиск top_k
    top_pairs, passages_list = search_faiss_index(file_id, pipeline_used, query_emb, request.top_k)
    top_passages = [passages_list[i] for i, _ in top_pairs]
    # LLM
    prompt = build_prompt(top_passages, request.question)
    llm_response = ask_llm(prompt)
    answer = llm_response.strip()
    return QueryResult(answer=answer, passages=top_passages)

@app.get("/download-markdown/{job_id}")
async def download_markdown(job_id: str):
    """Return the converted Markdown file for the specified job as a file download."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    file_id = job.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="У задачи нет связанного файла")
    md_path = os.path.join("data", "markdown", f"{file_id}.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Markdown-файл не найден")
    return FileResponse(md_path, filename=f"{file_id}.md", media_type="text/markdown")

# ==== Background tasks ====

async def process_file_job(job_id, orig_path, file_id, pipeline):
    try:
        logger.info("[process_file_job] Start job %s (file_id=%s)", job_id, file_id)
        jobs[job_id]["status"] = "converting"
        _update_job(job_id, progress=0.1, detail="Загрузка файла")
        md_path = os.path.join("data", "markdown", f"{file_id}.md")
        # Определяем расширение исходного файла
        ext = os.path.splitext(orig_path)[1].lower().lstrip(".")

        # Если уже Markdown — пропускаем конвертацию
        if ext == "md":
            # Убедимся, что директория существует
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            shutil.copyfile(orig_path, md_path)
            real_pipeline = "markdown"
        else:
            _update_job(job_id, progress=0.2, detail="DocLing/Markitdown: конвертация")
            # Конвертация в зависимости от выбранного pipeline
            real_pipeline = await asyncio.to_thread(convert_to_markdown, orig_path, md_path, pipeline)
        _update_job(job_id, progress=0.3, detail="Конвертация в Markdown")
        logger.debug("[process_file_job] Converted to markdown via %s: %s", real_pipeline, md_path)
        # Чтение markdown
        with open(md_path, encoding="utf-8") as f:
            md_text = f.read()
        # Чанкинг
        chunks = chunk_markdown(md_text)
        _update_job(job_id, progress=0.5, detail="Чанкинг Markdown")
        logger.debug("[process_file_job] Markdown chunked into %d chunks", len(chunks))
        # Эмбеддинги
        embeddings = await asyncio.to_thread(get_embeddings, chunks)
        _update_job(job_id, progress=0.7, detail="Вычисление эмбеддингов и индексация")
        logger.debug("[process_file_job] Created embeddings and index")
        # Индексация
        create_faiss_index(embeddings, chunks, file_id, real_pipeline)
        _update_job(job_id, progress=1.0, detail=f"Готово — pipeline: {real_pipeline}")
        jobs[job_id]["status"] = "ready"
    except Exception as e:
        logger.exception("[process_file_job] Job %s failed", job_id)
        jobs[job_id]["status"] = "error"
        _update_job(job_id, detail=str(e))

async def process_zip_job(job_id, pdfs, pipeline):
    try:
        logger.info("[process_zip_job] Start zip job %s with %d pdfs", job_id, len(pdfs))
        count = len(pdfs)
        for idx, (name, pdf_bytes) in enumerate(pdfs):
            file_id, orig_path = save_original_file(pdf_bytes, "pdf")
            md_path = os.path.join("data", "markdown", f"{file_id}.md")
            real_pipeline = await asyncio.to_thread(convert_to_markdown, orig_path, md_path, pipeline)
            with open(md_path, encoding="utf-8") as f:
                md_text = f.read()
            chunks = chunk_markdown(md_text)
            embeddings = await asyncio.to_thread(get_embeddings, chunks)
            create_faiss_index(embeddings, chunks, file_id, real_pipeline)
            jobs[job_id]["file_ids"].append(file_id)
            jobs[job_id]["done"] += 1
            _update_job(job_id, progress=jobs[job_id]["done"] / count, detail=f"Обработка файла {idx+1}/{count}")
            logger.debug("[process_zip_job] Processed file %s (%d/%d)", file_id, idx+1, count)
        _update_job(job_id, progress=1.0, detail=f"Готово — обработано файлов: {count}")
        jobs[job_id]["status"] = "ready"
    except Exception as e:
        logger.exception("[process_zip_job] Job %s failed", job_id)
        jobs[job_id]["status"] = "error"
        _update_job(job_id, detail=str(e))

# === New endpoint: upload multiple individual files ===

@app.post("/upload-files", response_model=UploadResponse)
async def upload_files(background_tasks: BackgroundTasks,
                       files: List[UploadFile] = File(...),
                       pipeline: str = Form("docling"),
                       project: str = Form("default")):
    if not files:
        raise HTTPException(status_code=400, detail="Файлы не переданы")
    for f in files:
        if not allowed_ext(f.filename):
            raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: {f.filename}")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0.0, "detail": None, "count": len(files), "done": 0, "file_ids": [], "pipeline": pipeline, "project": project}

    # Считываем содержимое файлов до закрытия соединения, чтобы избежать 'I/O operation on closed file'
    file_buffers = []  # list of tuples (bytes, ext)
    for f in files:
        file_bytes = await f.read()
        ext = f.filename.split(".")[-1].lower()
        file_buffers.append((file_bytes, ext))

    async def _process_batch():
        try:
            total = len(file_buffers)
            for idx, (file_bytes, ext) in enumerate(file_buffers):
                fid, orig_path = save_original_file(file_bytes, ext)
                md_path = os.path.join("data", "markdown", f"{fid}.md")
                real_pipeline = await asyncio.to_thread(convert_to_markdown, orig_path, md_path, pipeline)
                with open(md_path, encoding="utf-8") as fp:
                    md_text = fp.read()
                chunks = chunk_markdown(md_text)
                embeddings = await asyncio.to_thread(get_embeddings, chunks)
                create_faiss_index(embeddings, chunks, fid, real_pipeline)
                jobs[job_id]["file_ids"].append(fid)
                jobs[job_id]["done"] += 1
                _update_job(job_id, progress=jobs[job_id]["done"] / total, detail=f"Обработка файла {idx+1}/{total}")
            jobs[job_id]["status"] = "ready"
            _update_job(job_id, progress=1.0, detail="Готово")
        except Exception as e:
            logger.exception("[upload_files] batch failed")
            jobs[job_id]["status"] = "error"
            _update_job(job_id, detail=str(e))

    background_tasks.add_task(_process_batch)
    return UploadResponse(job_id=job_id)

# === Download bundle ===

@app.get("/download-bundle/{job_id}")
async def download_bundle(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    file_ids = job.get("file_ids", [])
    if not file_ids:
        raise HTTPException(status_code=400, detail="У задачи нет файлов")
    project = job.get("project", "project")
    zip_path = _zip_markdown(file_ids, project)
    return FileResponse(zip_path, filename=f"{project}.zip", media_type="application/zip") 