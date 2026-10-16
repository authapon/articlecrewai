"""CrewAI tool สำหรับเขียนไฟล์ (จำกัดให้เขียนได้เฉพาะในโฟลเดอร์ output)

มี guard กันกรณี LLM ส่งต่อเนื้อหาไม่ครบ (ย่อ/ตัดกลางทาง/ใส่ placeholder):
ไฟล์บทความ (article*.md และไฟล์ใน drafts/) ต้องยาวพอและมีส่วน 'แหล่งอ้างอิง'
"""
from pathlib import Path
from typing import Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import ARTICLE_OUTPUT_DIR, MIN_ARTICLE_CHARS

BASE_DIR = ARTICLE_OUTPUT_DIR.resolve()
ALLOWED_EXT = {".md", ".txt", ".json"}
REFERENCE_MARKERS = ("แหล่งอ้างอิง", "references", "sources")


def _is_article_file(target: Path) -> bool:
    rel = target.relative_to(BASE_DIR)
    return rel.parts[0] == "drafts" or rel.stem.lower().startswith("article")


def _validate_article(content: str) -> str | None:
    """คืนข้อความ error ถ้าเนื้อหาไม่ผ่านเกณฑ์ ไม่เช่นนั้นคืน None"""
    if len(content.strip()) < MIN_ARTICLE_CHARS:
        return (
            f"เนื้อหาสั้นผิดปกติ ({len(content.strip())} ตัวอักษร ต่ำกว่าขั้นต่ำ {MIN_ARTICLE_CHARS}) "
            "อาจถูกย่อหรือเป็น placeholder"
        )
    lowered = content.lower()
    if not any(m in lowered for m in REFERENCE_MARKERS):
        return "ไม่พบส่วน 'แหล่งอ้างอิง' ท้ายบทความ อาจถูกตัดกลางทาง"
    return None


class FileWriteInput(BaseModel):
    filename: str = Field(..., description="ชื่อไฟล์แบบ relative เช่น article.md หรือ drafts/draft_1.md")
    content: str = Field(..., description="เนื้อหาทั้งหมดที่ต้องการเขียนลงไฟล์ ต้องครบตามต้นฉบับ ห้ามย่อ")
    mode: Literal["overwrite", "append"] = Field("overwrite", description="overwrite หรือ append")


class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = (
        "เขียนข้อความลงไฟล์ในโฟลเดอร์ output (รองรับ .md .txt .json) "
        "ใช้บันทึกฉบับร่าง บทความฉบับสุดท้าย และรายงานผลตรวจ "
        "ไฟล์บทความจะถูกปฏิเสธถ้าเนื้อหาสั้นผิดปกติหรือไม่มีส่วนแหล่งอ้างอิง"
    )
    args_schema: Type[BaseModel] = FileWriteInput

    def _run(self, filename: str, content: str, mode: str = "overwrite") -> str:
        target = (BASE_DIR / filename).resolve()
        if BASE_DIR not in target.parents:
            return "[file_write] ปฏิเสธ: path ต้องอยู่ภายในโฟลเดอร์ output เท่านั้น"
        if target.suffix.lower() not in ALLOWED_EXT:
            return f"[file_write] ปฏิเสธ: รองรับเฉพาะนามสกุล {sorted(ALLOWED_EXT)}"
        if not content.strip():
            return "[file_write] ปฏิเสธ: เนื้อหาว่างเปล่า"

        if mode == "overwrite" and _is_article_file(target):
            problem = _validate_article(content)
            if problem:
                return (
                    f"[file_write] ปฏิเสธการบันทึก {filename}: {problem} "
                    "ไม่ได้บันทึกอะไรลงดิสก์ กรุณาแจ้ง Content Manager ให้ส่งบทความ 'ทั้งฉบับ' "
                    "ตามต้นฉบับทุกตัวอักษรมาใหม่ แล้วเรียก file_write อีกครั้ง"
                )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a" if mode == "append" else "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            return f"[file_write] เขียนไฟล์ไม่สำเร็จ: {e}"
        return f"บันทึกสำเร็จ: {target} ({len(content)} ตัวอักษร, mode={mode})"
