import streamlit as st
import requests
import time
import pandas as pd
import json

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocLing-Markitdown Service", layout="wide")
st.title("DocLing-Markitdown Service")

# Выбор pipeline
pipeline = st.selectbox("Pipeline для конвертации:", ["docling", "markitdown"])

# Загрузка файла или ZIP
st.header("Загрузка документа")
uploaded_file = st.file_uploader("Выберите файл (PDF, DOCX, XLSX, PPTX, ZIP)", type=["pdf", "docx", "xlsx", "pptx", "zip"])

if uploaded_file:
    is_zip = uploaded_file.name.lower().endswith(".zip")
    if st.button("Загрузить и проанализировать"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
        with st.spinner("Загрузка и запуск анализа..."):
            if is_zip:
                resp = requests.post(f"{API_URL}/upload-zip", files=files, data={"pipeline": pipeline})
            else:
                resp = requests.post(f"{API_URL}/upload-file", files=files, data={"pipeline": pipeline})
            if resp.status_code != 200:
                st.error(f"Ошибка загрузки: {resp.text}")
            else:
                job_id = resp.json()["job_id"]
                st.session_state["job_id"] = job_id
                st.success(f"Задача {job_id} запущена!")

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
    elif data["status"] == "error":
        st.error(f"Ошибка: {data.get('detail','')}")

# Чат и параметры
if job_id and st.button("Показать чат и параметры"):
    st.header("Извлечение параметров школы")
    question = st.text_input("Ваш вопрос (например: 'Извлеките все параметры школы')", value="Извлеките все параметры школы")
    top_k = st.slider("Сколько фрагментов использовать?", 1, 10, 5)
    if st.button("Запросить LLM"):
        with st.spinner("Запрос к LLM..."):
            payload = {"question": question, "top_k": top_k, "pipeline": pipeline}
            resp = requests.post(f"{API_URL}/query", json=payload)
            if resp.status_code != 200:
                st.error(f"Ошибка запроса: {resp.text}")
            else:
                data = resp.json()
                answer = data["answer"]
                passages = data["passages"]
                st.subheader("Ответ LLM (параметры)")
                df = pd.DataFrame(list(answer.items()), columns=["Параметр", "Значение"])
                st.dataframe(df)
                st.download_button("Экспорт в CSV", df.to_csv(index=False).encode("utf-8"), file_name="school_params.csv", mime="text/csv")
                st.subheader("Использованные фрагменты Markdown")
                for i, passage in enumerate(passages):
                    st.markdown(f"**Фрагмент {i+1}:**\n\n" + passage) 