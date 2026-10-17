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
FINAL_ARTICLE_FILE = "article.md"  # ชื่อไฟล์บทความฉบับสุดท้าย (เขียนได้ผ่าน publish_article เท่านั้น)
SOURCES_FILE = Path(_get("SOURCES_FILE", "sources.md")).name  # เขียนได้ผ่าน sources_add เท่านั้น
ARCHIVE_PREVIOUS_RUN = _bool("ARCHIVE_PREVIOUS_RUN", True)  # ย้ายผลลัพธ์รอบก่อนไป output/archive/<เวลา>/
FILE_READ_MAX_CHARS = _int("FILE_READ_MAX_CHARS", 8000)  # ต่อการอ่าน 1 ครั้ง (อ่านต่อด้วย offset)

# ---------- ข้อกำหนดของบทความ ----------
# ขนาดนับเฉพาะเนื้อหา (ไม่รวมส่วน "แหล่งอ้างอิง") และไม่นับช่องว่าง/ขึ้นบรรทัดใหม่
ARTICLE_MIN_CHARS = _int("ARTICLE_MIN_CHARS", 3000)
ARTICLE_MAX_CHARS = _int("ARTICLE_MAX_CHARS", 8000)
# จำนวนแหล่งอ้างอิงขั้นต่ำที่ "ใช้ได้จริง" = ไม่ซ้ำกัน, ถูกอ้างในเนื้อหา, มี URL, (และมีอยู่ใน sources.md)
CITATION_MIN_COUNT = _int("CITATION_MIN_COUNT", 5)
CITATION_REQUIRE_IN_SOURCES = _bool("CITATION_REQUIRE_IN_SOURCES", True)
# "รอบ" = จำนวนครั้งที่ Content Writer แก้ไขฉบับร่าง
REVISION_MAX_ROUNDS = _int("REVISION_MAX_ROUNDS", 3)  # ครบแล้ว + citation ผ่าน → อนุโลมให้เผยแพร่
CITATION_MAX_FIX_ROUNDS = _int("CITATION_MAX_FIX_ROUNDS", 6)  # ครบแล้วยัง citation/ขนาดไม่ผ่าน → ไม่เผยแพร่

# ---------- Crew / บทความที่ต้องการ ----------
CREW_VERBOSE = _bool("CREW_VERBOSE", True)
# จำนวนรอบการคิด/เรียก tool สูงสุดต่อ agent (Manager ต้องสูงเพราะ delegate หลายครั้ง)
MANAGER_MAX_ITER = _int("MANAGER_MAX_ITER", 60)
AGENT_MAX_ITER = _int("AGENT_MAX_ITER", 30)
ARTICLE_TOPIC = _get("ARTICLE_TOPIC", "แนวโน้ม Local LLM สำหรับงาน Edge AI")
ARTICLE_AUDIENCE = _get("ARTICLE_AUDIENCE", "นักศึกษาและนักพัฒนาซอฟต์แวร์")
ARTICLE_LANGUAGE = _get("ARTICLE_LANGUAGE", "ภาษาไทย (ศัพท์เทคนิคใช้ภาษาอังกฤษได้)")


# ---------- ตรวจความสมเหตุสมผลของค่าที่ตั้ง ----------
def _fail(msg: str) -> None:
    raise SystemExit(f"[config] ค่าตั้งไม่ถูกต้อง: {msg}")


if ARTICLE_MIN_CHARS < 1:
    _fail("ARTICLE_MIN_CHARS ต้องมากกว่า 0")
if ARTICLE_MIN_CHARS > ARTICLE_MAX_CHARS:
    _fail(f"ARTICLE_MIN_CHARS ({ARTICLE_MIN_CHARS}) ต้องไม่เกิน ARTICLE_MAX_CHARS ({ARTICLE_MAX_CHARS})")
if CITATION_MIN_COUNT < 1:
    _fail("CITATION_MIN_COUNT ต้องมากกว่า 0")
if REVISION_MAX_ROUNDS < 0:
    _fail("REVISION_MAX_ROUNDS ต้องไม่ติดลบ")
if CITATION_MAX_FIX_ROUNDS < REVISION_MAX_ROUNDS:
    print(
        f"[config] CITATION_MAX_FIX_ROUNDS ({CITATION_MAX_FIX_ROUNDS}) น้อยกว่า REVISION_MAX_ROUNDS "
        f"({REVISION_MAX_ROUNDS}) ปรับเป็น {REVISION_MAX_ROUNDS}",
        file=sys.stderr,
    )
    CITATION_MAX_FIX_ROUNDS = REVISION_MAX_ROUNDS
