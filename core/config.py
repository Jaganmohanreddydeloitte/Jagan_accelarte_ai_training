"""
Project configuration — loads environment variables, defines paths,
and auto-detects the active LLM provider.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ─── Load .env ───────────────────────────────────────────────────────────────
load_dotenv()

# ─── Folder Paths ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LANDING_DIR = DATA_DIR / "landing"
PROFILES_DIR = DATA_DIR / "profiles"
STTM_DIR = DATA_DIR / "sttm"
BRONZE_DIR = DATA_DIR / "bronze_layer"
SILVER_DIR = DATA_DIR / "silver_layer"
GOLD_DIR = DATA_DIR / "gold_layer"
REPORTS_DIR = BASE_DIR / "reports"
AUDIT_DIR = BASE_DIR / "audit_logs"
CHROMA_DIR = BASE_DIR / ".chroma"

# ─── API Keys & Models ──────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini")
GITHUB_BASE_URL = "https://models.inference.ai.azure.com"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")

# ─── Auto-detect LLM Provider ───────────────────────────────────────────────
def _detect_provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").lower()
    if explicit:
        return explicit
    if GITHUB_TOKEN:
        return "github"
    if OPENAI_API_KEY:
        return "openai"
    if GROQ_API_KEY:
        return "groq"
    if GOOGLE_API_KEY:
        return "gemini"
    return "gemini"


LLM_PROVIDER = _detect_provider()

# ─── Create Directories ─────────────────────────────────────────────────────
for _dir in [
    DATA_DIR, LANDING_DIR, PROFILES_DIR, STTM_DIR,
    BRONZE_DIR, SILVER_DIR, GOLD_DIR,
    REPORTS_DIR, AUDIT_DIR, CHROMA_DIR,
]:
    _dir.mkdir(parents=True, exist_ok=True)
