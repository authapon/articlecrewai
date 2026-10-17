"""ตัวช่วยจัดการ path ให้เข้าถึงได้เฉพาะภายใน ARTICLE_OUTPUT_DIR"""
from pathlib import Path

from config import ARTICLE_OUTPUT_DIR, SOURCES_FILE

BASE_DIR: Path = ARTICLE_OUTPUT_DIR.resolve()
SOURCES_PATH: Path = BASE_DIR / SOURCES_FILE
ALLOWED_EXT = {".md", ".txt", ".json"}


def resolve_in_output(filename: str) -> Path | None:
    """คืน path จริงถ้าอยู่ภายใน output dir ไม่เช่นนั้นคืน None (กัน path traversal)"""
    target = (BASE_DIR / filename).resolve()
    return target if BASE_DIR in target.parents else None
