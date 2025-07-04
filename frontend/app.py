import streamlit as st
import requests
import time
import pandas as pd
import json

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocLing-Markitdown Service", layout="wide")
st.title("DocLing-Markitdown Service")

# Имя проекта
project_name = st.text_input("Имя проекта", value="my_project")

# Выбор pipeline
pipeline = st.selectbox("Pipeline:", ["docling", "markitdown", "markdown"])

# Загрузка файла или ZIP
st.header("Загрузка документа")
uploaded_files = st.file_uploader(
    "Выберите один или несколько файлов (PDF, DOCX, XLSX, PPTX, MD, ZIP)",
    type=["pdf", "docx", "xlsx", "pptx", "md", "zip"],
    accept_multiple_files=True,
)

if uploaded_files:
    if st.button("Загрузить и проанализировать"):
        with st.spinner("Загрузка и запуск анализа..."):
            if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".zip"):
                uf = uploaded_files[0]
                files = {"file": (uf.name, uf.getvalue())}
                resp = requests.post(
                    f"{API_URL}/upload-zip",
                    files=files,
                    data={"pipeline": pipeline, "project": project_name},
                )
            elif len(uploaded_files) == 1:
                uf = uploaded_files[0]
                files = {"file": (uf.name, uf.getvalue())}
                resp = requests.post(
                    f"{API_URL}/upload-file",
                    files=files,
                    data={"pipeline": pipeline, "project": project_name},
                )
            else:
                # multiple individual files
                multiple_files = [(f"files", (f.name, f.getvalue())) for f in uploaded_files]
                resp = requests.post(
                    f"{API_URL}/upload-files",
                    files=multiple_files,
                    data={"pipeline": pipeline, "project": project_name},
                )
            if resp.status_code != 200:
                st.error(f"Ошибка загрузки: {resp.text}")
            else:
                job_id = resp.json()["job_id"]
                st.session_state["job_id"] = job_id
                st.session_state["pipeline_used"] = pipeline
                st.success(f"Задача {job_id} запущена для проекта '{project_name}'!")

# Прогресс-бар
job_id = st.session_state.get("job_id")
if job_id:
    st.header("Прогресс анализа")
    status_area = st.empty()
    progress_bar = st.progress(0.0)
    while True:
        resp = requests.get(f"{API_URL}/job-status/{job_id}")
        if resp.status_code != 200:
            status_area.error("Ошибка статуса задачи")
            break
        data = resp.json()
        progress_bar.progress(data["progress"])
        status_area.info(f"Статус: {data['status']} | {data.get('detail','')}")
        if data["status"] in ["ready", "error"]:
            break
        time.sleep(1)
    if data["status"] == "ready":
        st.success("Анализ завершён!")
        # Скачивание Markdown / ZIP
        # Если задача содержит несколько файлов, берём bundle
        dl_url = f"{API_URL}/download-bundle/{job_id}"
        dl_resp = requests.get(dl_url)
        if dl_resp.status_code == 200:
            st.download_button(
                "Скачать Markdown (ZIP)",
                dl_resp.content,
                file_name=f"{project_name}.zip",
                mime="application/zip",
            )
        else:
            # Fallback: одиночный md
            dl_resp = requests.get(f"{API_URL}/download-markdown/{job_id}")
            if dl_resp.status_code == 200:
                st.download_button(
                    "Скачать Markdown", dl_resp.content, file_name=f"{project_name}.md", mime="text/markdown"
                )
            else:
                st.warning("Не удалось получить результат: " + dl_resp.text)
    elif data["status"] == "error":
        st.error(f"Ошибка: {data.get('detail','')}")

# Чат и параметры
pipeline_used = st.session_state.get("pipeline_used", pipeline)

if job_id and st.button("Показать чат и параметры"):
    st.header("Извлечение параметров школы")
    question = st.text_input("Ваш вопрос (например: 'Извлеките все параметры школы')", value="Извлеките все параметры школы")
    top_k = st.slider("Сколько фрагментов использовать?", 1, 50, 10)
    if st.button("Запросить LLM"):
        with st.spinner("Запрос к LLM..."):
            payload = {"question": question, "top_k": top_k, "pipeline": pipeline_used}
            resp = requests.post(f"{API_URL}/query", json=payload)
            if resp.status_code != 200:
                st.error(f"Ошибка запроса: {resp.text}")
            else:
                data = resp.json()
                answer = data["answer"]
                passages = data["passages"]
                st.subheader("Ответ LLM")
                if isinstance(answer, dict):
                    df = pd.DataFrame(list(answer.items()), columns=["Ключ", "Значение"])
                    st.dataframe(df)
                else:
                    st.markdown(answer)
                st.subheader("Использованные фрагменты Markdown")
                for i, passage in enumerate(passages):
                    st.markdown(f"**Фрагмент {i+1}:**\n\n" + passage) 