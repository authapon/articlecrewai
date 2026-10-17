"""CrewAI tool สำหรับตรวจขนาดและ citation ของบทความ (นับด้วยโค้ด ไม่ใช่ LLM)"""
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import (
    ARTICLE_MAX_CHARS,
    ARTICLE_MIN_CHARS,
    CITATION_MIN_COUNT,
    CITATION_REQUIRE_IN_SOURCES,
)
from tools.citations import analyze, format_report, load_sources
from tools.fs_utils import SOURCES_PATH, resolve_in_output


class ArticleCheckInput(BaseModel):
    filename: str = Field(..., description="ไฟล์บทความที่ต้องการตรวจ เช่น drafts/draft_1.md")


class ArticleCheckTool(BaseTool):
    name: str = "article_check"
    description: str = (
        "ตรวจบทความจากไฟล์ในโฟลเดอร์ output: นับตัวอักษรเนื้อหา, นับ citation ที่ใช้ได้จริง "
        "(ไม่ซ้ำ ถูกอ้างในเนื้อหา มี URL และมีอยู่ใน sources.md), หา citation ที่ไม่มีนิยามหรือใช้ไม่ได้ "
        "แล้วสรุป CITATION_VERDICT และ SIZE_VERDICT ให้ใช้ตัวเลขจากเครื่องมือนี้เท่านั้น ห้ามนับเอง"
    )
    args_schema: Type[BaseModel] = ArticleCheckInput

    def _run(self, filename: str) -> str:
        target = resolve_in_output(filename)
        if target is None:
            return "[article_check] ปฏิเสธ: path ต้องอยู่ภายในโฟลเดอร์ output เท่านั้น"
        if not target.is_file():
            return f"[article_check] ไม่พบไฟล์: {filename} (ต้องให้ Publisher บันทึกฉบับร่างก่อน)"
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return f"[article_check] อ่านไฟล์ไม่สำเร็จ: {e}"
        report = analyze(
            text,
            load_sources(SOURCES_PATH),
            min_chars=ARTICLE_MIN_CHARS,
            max_chars=ARTICLE_MAX_CHARS,
            min_citations=CITATION_MIN_COUNT,
            require_in_sources=CITATION_REQUIRE_IN_SOURCES,
        )
        return format_report(report, filename)
