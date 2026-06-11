from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.chatbot import answer_question
from app.config import CHAT_BACKEND, OLLAMA_MODEL
from app.logger import get_stats, log_chat, read_logs
from app.models import ChatRequest, ChatResponse, DocumentInfo
from app.retriever import load_index, search, summarize_sources


app = FastAPI(title="School Local Chatbot", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": CHAT_BACKEND, "model": OLLAMA_MODEL}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/documents", response_model=list[DocumentInfo])
def documents() -> list[DocumentInfo]:
    index = load_index()
    if index is None:
        return []
    return [DocumentInfo(source=source, chunks=chunks) for source, chunks in summarize_sources(index)]


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    index = load_index()
    if index is None:
        raise HTTPException(
            status_code=400,
            detail="Search index is missing or outdated. Run `python -m app.ingest` after changing files in src/.",
        )

    results = search(index, payload.question, history=payload.history)
    response = answer_question(payload.question, results, payload.history)

    try:
        log_chat(payload.question, response)
    except Exception:
        pass  # อย่าให้ระบบ log ทำให้แชทล้ม

    return response


# ═══════════════════════════════════════════════════
# ADMIN — สำหรับเก็บข้อมูลวิเคราะห์ (หลังบ้าน)
# ═══════════════════════════════════════════════════
@app.get("/admin/logs")
def admin_logs(limit: int = 100) -> list[dict]:
    """ดู log การถาม-ตอบล่าสุด N รายการ"""
    return read_logs(limit=limit)


@app.get("/admin/stats")
def admin_stats() -> dict:
    """สรุปสถิติการใช้งาน: จำนวนคำถาม, สัดส่วน grounded, คำถามยอดฮิต"""
    return get_stats()
