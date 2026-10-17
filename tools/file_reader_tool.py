"""CrewAI tool สำหรับอ่านไฟล์ (read-only) ภายในโฟลเดอร์ output"""
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import FILE_READ_MAX_CHARS
from tools.fs_utils import ALLOWED_EXT, resolve_in_output


class FileReadInput(BaseModel):
    filename: str = Field(..., description="ชื่อไฟล์แบบ relative เช่น sources.md หรือ drafts/draft_1.md")
    offset: int = Field(0, description="ตำแหน่งตัวอักษรที่เริ่มอ่าน (ใช้อ่านต่อเมื่อไฟล์ยาวกว่าที่แสดง)")


class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = (
        "อ่านไฟล์ข้อความในโฟลเดอร์ output (เช่น sources.md, drafts/draft_1.md) แบบอ่านอย่างเดียว "
        f"แสดงครั้งละไม่เกิน {FILE_READ_MAX_CHARS} ตัวอักษร ถ้ามีต่อให้เรียกซ้ำพร้อม offset ที่ระบุท้ายผลลัพธ์"
    )
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, filename: str, offset: int = 0) -> str:
        target = resolve_in_output(filename)
        if target is None:
            return "[file_read] ปฏิเสธ: path ต้องอยู่ภายในโฟลเดอร์ output เท่านั้น"
        if target.suffix.lower() not in ALLOWED_EXT:
            return f"[file_read] ปฏิเสธ: รองรับเฉพาะนามสกุล {sorted(ALLOWED_EXT)}"
        if not target.is_file():
            return f"[file_read] ไม่พบไฟล์: {filename}"
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return f"[file_read] อ่านไฟล์ไม่สำเร็จ: {e}"

        offset = max(0, offset)
        chunk = text[offset: offset + FILE_READ_MAX_CHARS]
        end = offset + len(chunk)
        head = f"[file_read] {filename} ตัวอักษรที่ {offset}-{end} จากทั้งหมด {len(text)}"
        if end < len(text):
            head += f" (ยังมีต่อ: เรียกซ้ำด้วย offset={end})"
        return f"{head}\n---\n{chunk}"
