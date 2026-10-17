"""CrewAI tool สำหรับเขียนไฟล์ทั่วไป (ฉบับร่าง รายงานผลตรวจ) ภายในโฟลเดอร์ output

ข้อจำกัดโดยเจตนา:
  - sources.md เขียนได้ผ่าน sources_add เท่านั้น (กันเลข ID และ URL ถูกแก้/สร้างโดย LLM)
  - บทความฉบับสุดท้าย (article.md) เขียนได้ผ่าน publish_article เท่านั้น
    เพราะต้องผ่านการตรวจ citation และขนาด และถูกเรียงเลข citation ใหม่
  - ไฟล์ใน drafts/ ต้องไม่ใช่ placeholder: ยาวพอและมีส่วน 'แหล่งอ้างอิง' (กันกรณี LLM ย่อ/ตัดเนื้อหา)
"""
from typing import Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import ARTICLE_MIN_CHARS, FINAL_ARTICLE_FILE, SOURCES_FILE
from tools.citations import parse_article
from tools.fs_utils import ALLOWED_EXT, BASE_DIR, resolve_in_output

DRAFT_MIN_CHARS = min(500, ARTICLE_MIN_CHARS)  # ขั้นต่ำสำหรับฉบับร่าง (กัน placeholder/ถูกย่อ)


class FileWriteInput(BaseModel):
    filename: str = Field(..., description="ชื่อไฟล์แบบ relative เช่น drafts/draft_1.md หรือ review_report.md")
    content: str = Field(..., description="เนื้อหาทั้งหมดที่ต้องการเขียนลงไฟล์ ต้องครบตามต้นฉบับ ห้ามย่อ")
    mode: Literal["overwrite", "append"] = Field("overwrite", description="overwrite หรือ append")


class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = (
        "เขียนข้อความลงไฟล์ในโฟลเดอร์ output (รองรับ .md .txt .json) ใช้บันทึกฉบับร่าง (drafts/draft_N.md) "
        "และรายงานผลตรวจ (review_report.md) ห้ามใช้เขียน sources.md และ article.md "
        "(article.md ต้องใช้ publish_article) ฉบับร่างจะถูกปฏิเสธถ้าสั้นผิดปกติหรือไม่มีส่วนแหล่งอ้างอิง"
    )
    args_schema: Type[BaseModel] = FileWriteInput

    def _run(self, filename: str, content: str, mode: str = "overwrite") -> str:
        target = resolve_in_output(filename)
        if target is None:
            return "[file_write] ปฏิเสธ: path ต้องอยู่ภายในโฟลเดอร์ output เท่านั้น"
        if target.suffix.lower() not in ALLOWED_EXT:
            return f"[file_write] ปฏิเสธ: รองรับเฉพาะนามสกุล {sorted(ALLOWED_EXT)}"
        if not content.strip():
            return "[file_write] ปฏิเสธ: เนื้อหาว่างเปล่า"

        rel = target.relative_to(BASE_DIR)
        if rel.as_posix() == SOURCES_FILE:
            return f"[file_write] ปฏิเสธ: {SOURCES_FILE} จัดการโดยเครื่องมือ sources_add เท่านั้น"
        if len(rel.parts) == 1 and rel.stem.lower().startswith("article"):
            return (
                f"[file_write] ปฏิเสธ: ไฟล์บทความฉบับสุดท้าย ({FINAL_ARTICLE_FILE}) ต้องบันทึกผ่านเครื่องมือ "
                "publish_article เท่านั้น เพราะต้องผ่านการตรวจ citation และถูกเรียงเลขใหม่ "
                "(ถ้าเป็นฉบับร่างให้บันทึกที่ drafts/draft_N.md)"
            )

        if rel.parts[0] == "drafts" and mode == "overwrite":
            stripped = content.strip()
            if len(stripped) < DRAFT_MIN_CHARS:
                problem = f"เนื้อหาสั้นผิดปกติ ({len(stripped)} ตัวอักษร ต่ำกว่า {DRAFT_MIN_CHARS}) อาจถูกย่อหรือเป็น placeholder"
            elif parse_article(content).header_line is None:
                problem = "ไม่พบหัวข้อ 'แหล่งอ้างอิง' ท้ายบทความ อาจถูกตัดกลางทาง"
            else:
                problem = None
            if problem:
                return (
                    f"[file_write] ปฏิเสธการบันทึก {filename}: {problem} ไม่ได้บันทึกอะไรลงดิสก์ "
                    "กรุณาแจ้ง Content Manager ให้ส่งบทความ 'ทั้งฉบับ' ตามต้นฉบับทุกตัวอักษรมาใหม่ "
                    "แล้วเรียก file_write อีกครั้ง"
                )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a" if mode == "append" else "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            return f"[file_write] เขียนไฟล์ไม่สำเร็จ: {e}"
        return f"บันทึกสำเร็จ: {target} ({len(content)} ตัวอักษร, mode={mode})"
