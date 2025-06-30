import os
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from backend.models import UploadResponse, JobStatusResponse, QueryRequest, QueryResult
from backend.utils.file_ops import save_original_file, allowed_ext, extract_pdfs_from_zip, save_markdown_file
from backend.utils.conversion import convert_to_markdown
from backend.utils.embedding import chunk_markdown, get_embeddings
from backend.utils.faiss_index import create_faiss_index, search_faiss_index
from backend.utils.llm_chain import build_prompt, ask_llm, normalize_answer
import uuid
import json
from typing import Dict

app = FastAPI()

# Хранилище статусов задач (in-memory)
jobs: Dict[str, Dict] = {}

@app.post("/upload-file", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = None, pipeline: str = "docling"):
    # Проверяем расширение
    ext = file.filename.split(".")[-1].lower()
    if not allowed_ext(file.filename):
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")
    file_bytes = await file.read()
    file_id, orig_path = save_original_file(file_bytes, ext)
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0.0, "detail": None, "file_id": file_id, "pipeline": pipeline}
    background_tasks.add_task(process_file_job, job_id, orig_path, file_id, pipeline)
    return UploadResponse(job_id=job_id)

@app.post("/upload-zip", response_model=UploadResponse)
async def upload_zip(file: UploadFile = File(...), background_tasks: BackgroundTasks = None, pipeline: str = "docling"):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается ZIP-файл")
    zip_bytes = await file.read()
    pdfs = extract_pdfs_from_zip(zip_bytes)
    if not pdfs:
        raise HTTPException(status_code=400, detail="В ZIP нет PDF-файлов")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0.0, "detail": None, "zip": True, "count": len(pdfs), "done": 0, "file_ids": [], "pipeline": pipeline}
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
    for job in reversed(list(jobs.values())):
        if job.get("file_id") and job["pipeline"] == request.pipeline:
            file_id = job["file_id"]
            break
    if not file_id:
        raise HTTPException(status_code=404, detail="Нет обработанных файлов для этого pipeline")
    # Загружаем индекс и markdown-фрагменты
    from backend.utils.faiss_index import load_faiss_index
    index, passages = load_faiss_index(file_id, request.pipeline)
    # Получаем эмбеддинг вопроса
    from backend.utils.embedding import get_embeddings
    query_emb = get_embeddings([request.question])[0]
    # Поиск top_k
    top_pairs, passages_list = search_faiss_index(file_id, request.pipeline, query_emb, request.top_k)
    top_passages = [passages_list[i] for i, _ in top_pairs]
    # LLM
    prompt = build_prompt(top_passages, request.question)
    llm_response = ask_llm(prompt)
    try:
        llm_json = json.loads(llm_response)
    except Exception:
        llm_json = {}
    answer = normalize_answer(llm_json)
    return QueryResult(answer=answer, passages=top_passages)

# ==== Background tasks ====

async def process_file_job(job_id, orig_path, file_id, pipeline):
    try:
        jobs[job_id]["status"] = "converting"
        jobs[job_id]["progress"] = 0.1
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
            # Конвертация в зависимости от выбранного pipeline
            real_pipeline = convert_to_markdown(orig_path, md_path, pipeline)
        jobs[job_id]["progress"] = 0.3
        # Чтение markdown
        with open(md_path, encoding="utf-8") as f:
            md_text = f.read()
        # Чанкинг
        chunks = chunk_markdown(md_text)
        jobs[job_id]["progress"] = 0.5
        # Эмбеддинги
        embeddings = get_embeddings(chunks)
        jobs[job_id]["progress"] = 0.7
        # Индексация
        create_faiss_index(embeddings, chunks, file_id, real_pipeline)
        jobs[job_id]["progress"] = 1.0
        jobs[job_id]["status"] = "ready"
        jobs[job_id]["detail"] = f"Pipeline: {real_pipeline}"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["detail"] = str(e)

async def process_zip_job(job_id, pdfs, pipeline):
    try:
        count = len(pdfs)
        for idx, (name, pdf_bytes) in enumerate(pdfs):
            file_id, orig_path = save_original_file(pdf_bytes, "pdf")
            md_path = os.path.join("data", "markdown", f"{file_id}.md")
            real_pipeline = convert_to_markdown(orig_path, md_path, pipeline)
            with open(md_path, encoding="utf-8") as f:
                md_text = f.read()
            chunks = chunk_markdown(md_text)
            embeddings = get_embeddings(chunks)
            create_faiss_index(embeddings, chunks, file_id, real_pipeline)
            jobs[job_id]["file_ids"].append(file_id)
            jobs[job_id]["done"] += 1
            jobs[job_id]["progress"] = jobs[job_id]["done"] / count
        jobs[job_id]["status"] = "ready"
        jobs[job_id]["detail"] = f"Обработано файлов: {count}"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["detail"] = str(e) 