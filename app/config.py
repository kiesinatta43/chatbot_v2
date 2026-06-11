import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
INDEX_PATH = DATA_DIR / "index.pkl"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = 4
MIN_RELEVANCE_SCORE = 0.08
MAX_HISTORY_TURNS = 6

CHAT_BACKEND = os.getenv("CHAT_BACKEND", "extractive")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "90"))

# Google Gemini (ใช้เมื่อ CHAT_BACKEND=gemini) — ตอบแบบสรุป/อธิบายจากบริบทเอกสารโดย LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = os.getenv(
    "GEMINI_URL",
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
)
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
