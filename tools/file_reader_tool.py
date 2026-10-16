"""CrewAI tool สำหรับอ่านไฟล์ (จำกัดให้อ่านได้เฉพาะในโฟลเดอร์ output)

ใช้ให้ผู้ตรวจเปิดอ่านบทความฉบับร่าง/ฉบับสุดท้ายจากดิสก์โดยตรง แทนการพึ่งข้อความที่ Manager พิมพ์ส่งต่อ
ซึ่งอาจเพี้ยนจากต้นฉบับ ไฟล์ยาวอ่านทีละช่วงได้ด้วย offset
"""
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import ARTICLE_OUTPUT_DIR, FILE_READ_MAX_CHARS

BASE_DIR = ARTICLE_OUTPUT_DIR.resolve()
ALLOWED_EXT = {".md", ".txt", ".json"}
MAX_CHARS_LIMIT = 20000


def _list_dir(target) -> str:
    files = sorted(
        str(p.relative_to(BASE_DIR))
        for p in target.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT
    )
    if not files:
        return "[file_read] ยังไม่มีไฟล์ในโฟลเดอร์ output"
    return "ไฟล์ที่อ่านได้:\n" + "\n".join(f"- {f}" for f in files)


class FileReadInput(BaseModel):
    filename: str = Field(
        ...,
        description="ชื่อไฟล์แบบ relative เช่น article.md หรือ drafts/draft_1.md (ใส่ '.' เพื่อดูรายชื่อไฟล์ทั้งหมด)",
    )
    offset: int = Field(0, ge=0, description="ตำแหน่งตัวอักษรที่เริ่มอ่าน ใช้อ่านไฟล์ยาวต่อจากช่วงก่อนหน้า (default 0)")
    max_chars: int = Field(
        FILE_READ_MAX_CHARS,
        ge=1,
        description=f"จำนวนตัวอักษรสูงสุดที่อ่านต่อครั้ง (สูงสุด {MAX_CHARS_LIMIT})",
    )


class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = (
        "อ่านเนื้อหาไฟล์ในโฟลเดอร์ output (รองรับ .md .txt .json) "
        "ใช้เปิดอ่านบทความฉบับร่างหรือฉบับสุดท้ายเพื่อตรวจสอบ ไฟล์ยาวจะถูกแบ่งเป็นช่วง "
        "ให้เรียกซ้ำพร้อม offset ที่ระบุท้ายผลลัพธ์จนกว่าจะอ่านครบ"
    )
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, filename: str, offset: int = 0, max_chars: int = FILE_READ_MAX_CHARS) -> str:
        target = (BASE_DIR / filename).resolve()
        if target != BASE_DIR and BASE_DIR not in target.parents:
            return "[file_read] ปฏิเสธ: path ต้องอยู่ภายในโฟลเดอร์ output เท่านั้น"
        if target.is_dir():
            return _list_dir(target)
        if target.suffix.lower() not in ALLOWED_EXT:
            return f"[file_read] ปฏิเสธ: รองรับเฉพาะนามสกุล {sorted(ALLOWED_EXT)}"
        if not target.is_file():
            return f"[file_read] ไม่พบไฟล์ {filename} (ใช้ filename='.' เพื่อดูรายชื่อไฟล์ที่มี)"

        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return f"[file_read] อ่านไฟล์ไม่สำเร็จ: {e}"

        total = len(text)
        offset = max(0, offset)
        if offset >= total and total > 0:
            return f"[file_read] offset {offset} เกินความยาวไฟล์ ({total} ตัวอักษร)"
        limit = max(1, min(max_chars, MAX_CHARS_LIMIT))
        chunk = text[offset : offset + limit]
        end = offset + len(chunk)

        header = f"[file_read] {filename} ตัวอักษร {offset}-{end} จากทั้งหมด {total}"
        if end < total:
            footer = f"\n\n[ยังอ่านไม่ครบ: เรียก file_read ซ้ำด้วย offset={end} เพื่ออ่านต่อ]"
        else:
            footer = "\n\n[จบไฟล์]"
        return f"{header}\n\n{chunk}{footer}"
