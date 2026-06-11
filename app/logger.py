"""บันทึก log การถาม-ตอบ ไว้สำหรับเก็บข้อมูลหลังบ้าน (วิเคราะห์/อ้างอิงในวิทยานิพนธ์)"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR
from app.models import ChatResponse

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "chat_logs.jsonl"

_lock = threading.Lock()


def log_chat(question: str, response: ChatResponse, extra: dict | None = None) -> None:
    """เขียน 1 บรรทัด JSON ต่อการสนทนา 1 ครั้ง ลงไฟล์ data/logs/chat_logs.jsonl"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": response.answer,
        "grounded": response.grounded,
        "citations": [c.source for c in response.citations],
        "citation_count": len(response.citations),
    }
    if extra:
        entry.update(extra)

    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_logs(limit: int | None = None) -> list[dict]:
    """อ่าน log ทั้งหมด (หรือ N รายการล่าสุด) — ใช้กับหน้า /admin/logs"""
    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open("r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    if limit:
        return lines[-limit:]
    return lines


def get_stats() -> dict:
    """สรุปสถิติการใช้งานคร่าวๆ — จำนวนคำถามทั้งหมด, สัดส่วน grounded, คำถามยอดฮิต"""
    logs = read_logs()
    total = len(logs)
    grounded = sum(1 for entry in logs if entry.get("grounded"))

    question_counts: dict[str, int] = {}
    for entry in logs:
        q = entry.get("question", "").strip()
        if q:
            question_counts[q] = question_counts.get(q, 0) + 1

    top_questions = sorted(question_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total_questions": total,
        "grounded_count": grounded,
        "grounded_ratio": round(grounded / total, 3) if total else 0,
        "ungrounded_count": total - grounded,
        "top_questions": [{"question": q, "count": c} for q, c in top_questions],
    }
