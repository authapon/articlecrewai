"""การตั้งค่าทั้งหมดของโปรเจกต์ อ่านจาก environment variable และไฟล์ .env

ลำดับความสำคัญ (สูง → ต่ำ):
  1. environment variable ของระบบ/เชลล์
  2. ค่าในไฟล์ .env (โฟลเดอร์เดียวกับ config.py)
  3. ค่า default ในไฟล์นี้

ค่าที่เว้นว่างไว้ (เช่น `SEARXNG_URL=`) ถือว่าไม่ได้ตั้ง และจะใช้ค่า default
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env", override=False)  # override=False: env ของระบบมาก่อน .env


def _get(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or not value.strip() else value.strip()


def _warn(name: str, raw: str, default) -> None:
    print(f"[config] ค่า {name}={raw!r} ไม่ถูกต้อง ใช้ค่า default: {default}", file=sys.stderr)


def _int(name: str, default: int) -> int:
    raw = _get(name, str(default))
    try:
        return int(raw)
    except ValueError:
        _warn(name, raw, default)
        return default


def _float(name: str, default: float) -> float:
    raw = _get(name, str(default))
    try:
        return float(raw)
    except ValueError:
        _warn(name, raw, default)
        return default


def _bool(name: str, default: bool) -> bool:
    raw = _get(name, "true" if default else "false").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    _warn(name, raw, default)
    return default


def _path(name: str, default: str) -> Path:
    p = Path(_get(name, default)).expanduser()
    return p if p.is_absolute() else (PROJECT_DIR / p).resolve()


# ---------- LLM (LM Studio / OpenAI API compatible) ----------
CREW_MODEL = _get("CREW_MODEL", "openai/qwen3.5-4b")
LMSTUDIO_BASE_URL = _get("LMSTUDIO_BASE_URL", "http://127.0.0.1:14900/v1")
LMSTUDIO_API_KEY = _get("LMSTUDIO_API_KEY", "lm-studio")
CREW_TEMPERATURE = _float("CREW_TEMPERATURE", 0.3)
CREW_MAX_TOKENS = _int("CREW_MAX_TOKENS", 8192)

# ---------- SearXNG ----------
SEARXNG_URL = _get("SEARXNG_URL", "http://127.0.0.1:3001").rstrip("/")
SEARXNG_TIMEOUT = _int("SEARXNG_TIMEOUT", 20)
SEARXNG_MAX_RESULTS = _int("SEARXNG_MAX_RESULTS", 5)
SEARXNG_LANGUAGE = _get("SEARXNG_LANGUAGE", "")  # เช่น th, en, auto; ว่าง = ไม่ส่งพารามิเตอร์

# ---------- Web fetch ----------
WEB_FETCH_TIMEOUT = _int("WEB_FETCH_TIMEOUT", 20)
WEB_FETCH_MAX_BYTES = _int("WEB_FETCH_MAX_BYTES", 2_000_000)
WEB_FETCH_MAX_CHARS = _int("WEB_FETCH_MAX_CHARS", 6000)
WEB_FETCH_MAX_REDIRECTS = _int("WEB_FETCH_MAX_REDIRECTS", 3)
WEB_FETCH_USER_AGENT = _get("WEB_FETCH_USER_AGENT", "Mozilla/5.0 (compatible; ArticleCrewBot/1.0)")
ALLOW_PRIVATE_FETCH = _bool("ALLOW_PRIVATE_FETCH", False)

# ---------- File output ----------
ARTICLE_OUTPUT_DIR = _path("ARTICLE_OUTPUT_DIR", "output")  # path แบบ relative อิงจากโฟลเดอร์โปรเจกต์
MIN_ARTICLE_CHARS = _int("MIN_ARTICLE_CHARS", 500)

# ---------- Crew / บทความที่ต้องการ ----------
CREW_VERBOSE = _bool("CREW_VERBOSE", True)
ARTICLE_TOPIC = _get("ARTICLE_TOPIC", "แนวโน้ม Local LLM สำหรับงาน Edge AI")
ARTICLE_AUDIENCE = _get("ARTICLE_AUDIENCE", "นักศึกษาและนักพัฒนาซอฟต์แวร์")
ARTICLE_LANGUAGE = _get("ARTICLE_LANGUAGE", "ภาษาไทย (ศัพท์เทคนิคใช้ภาษาอังกฤษได้)")
