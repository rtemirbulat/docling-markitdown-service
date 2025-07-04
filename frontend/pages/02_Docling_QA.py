import streamlit as st
import requests
import time
import os

# ---------- Config ----------
DEFAULT_API_URL = os.getenv("DOCMARK_API_URL", "http://localhost:8000")

st.set_page_config(page_title="DocLing-Markdown Q&A", layout="wide")

st.title("📄 ➡️ 🧠 Q&A по документу (DocLing/Markitdown)")

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Настройки")
    api_url = st.text_input("URL backend-сервиса", value=DEFAULT_API_URL)
    project_name = st.text_input("Имя проекта", value="my_project")
    pipeline = st.selectbox("Pipeline", ["docling", "markitdown", "markdown"], index=0)
    top_k = st.slider("Top-K фрагментов", 1, 50, 10)

# ---------- Upload block ----------
uploaded_file = st.file_uploader(
    "Загрузите документ (PDF, DOCX, PPTX, XLSX, MD)",
    type=["pdf", "docx", "pptx", "xlsx", "md"],
)

if uploaded_file and st.button("Загрузить и проанализировать", type="primary"):
    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
    with st.spinner("Отправка файла и запуск обработки…"):
        try:
            resp = requests.post(
                f"{api_url}/upload-file",
                files=files,
                data={"pipeline": pipeline, "project": project_name},
                timeout=120,
            )
            if resp.status_code != 200:
                st.error(f"Ошибка загрузки: {resp.text}")
            else:
                job_id = resp.json()["job_id"]
                st.session_state["job_id"] = job_id
                st.session_state["pipeline_used"] = pipeline
                st.success(f"Задача {job_id} запущена!")
        except Exception as e:
            st.error(f"Не удалось связаться с backend: {e}")

# ---------- Job progress ----------
job_id = st.session_state.get("job_id")
if job_id:
    prog_placeholder = st.empty()
    progbar = st.progress(0.0)
    while True:
        try:
            r = requests.get(f"{api_url}/job-status/{job_id}")
        except Exception as e:
            st.error(f"Ошибка связи с backend: {e}")
            break
        if r.status_code != 200:
            st.error(f"Ошибка статуса задачи: {r.text}")
            break
        data = r.json()
        progbar.progress(data["progress"])
        prog_placeholder.info(f"Статус: {data['status']} | {data.get('detail', '')}")
        if data["status"] in ("ready", "error"):
            break
        time.sleep(1)
    if data["status"] == "ready":
        st.success("Файл проанализирован!💡 Теперь можно задавать вопросы.")
    elif data["status"] == "error":
        st.error(f"Ошибка обработки: {data.get('detail','')} ")

# ---------- Chat interface ----------
if job_id and st.session_state.get("pipeline_used") and (data and data.get("status") == "ready"):
    st.markdown("---")
    st.subheader("💬 Чат с LLM по документу")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    user_question = st.chat_input("Задайте вопрос по документу…")

    if user_question:
        # Display user message immediately
        st.chat_message("user").markdown(user_question)
        with st.spinner("LLM думает…"):
            payload = {
                "question": user_question,
                "top_k": top_k,
                "pipeline": st.session_state["pipeline_used"],
            }
            try:
                resp = requests.post(f"{api_url}/query", json=payload, timeout=120)
            except Exception as e:
                st.chat_message("assistant").error(f"Ошибка запроса к backend: {e}")
                resp = None
            if resp is None or resp.status_code != 200:
                err = resp.text if resp is not None else ""
                st.chat_message("assistant").error(f"Backend вернул ошибку: {err}")
            else:
                res = resp.json()
                answer = res["answer"]
                passages = res["passages"]
                st.chat_message("assistant").markdown(answer)
                with st.expander("Показать использованные фрагменты Markdown"):
                    for i, p in enumerate(passages, 1):
                        st.markdown(f"**Фрагмент {i}:**\n\n" + p)
                # Save history
                st.session_state.chat_history.append({"q": user_question, "a": answer})

    # Show history (last 3)
    if st.session_state.chat_history:
        st.markdown("---")
        st.markdown("**Предыдущие ответы:**")
        for qa in reversed(st.session_state.chat_history[-3:]):
            with st.expander(f"Q: {qa['q']}"):
                st.markdown(qa['a']) 