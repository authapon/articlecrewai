"""CrewAI tool สำหรับเผยแพร่บทความฉบับสุดท้าย (article.md)

ก่อนบันทึก tool จะ:
  1. ตรวจขนาดและ citation ด้วยโค้ด ถ้าไม่ผ่านจะไม่บันทึกอะไร และคืนเหตุผลทั้งหมดเพื่อแจ้ง Content Manager
  2. เรียงเลข citation ใหม่เป็น 1..k ตามลำดับที่ปรากฏ และสร้างรายการอ้างอิงใหม่ให้ตรงกัน
"""
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import (
    ARTICLE_MAX_CHARS,
    ARTICLE_MIN_CHARS,
    CITATION_MIN_COUNT,
    CITATION_REQUIRE_IN_SOURCES,
    FINAL_ARTICLE_FILE,
)
from tools.citations import analyze, format_report, load_sources, renumber
from tools.fs_utils import BASE_DIR, SOURCES_PATH


class PublishInput(BaseModel):
    content: str = Field(..., description="บทความฉบับสมบูรณ์ทั้งฉบับ (Markdown) ตามต้นฉบับทุกตัวอักษร ห้ามย่อ")


class PublishArticleTool(BaseTool):
    name: str = "publish_article"
    description: str = (
        f"เผยแพร่บทความฉบับสุดท้ายเป็น {FINAL_ARTICLE_FILE}: ตรวจขนาดและ citation ด้วยโค้ด "
        "เรียงเลข citation ใหม่ตามลำดับที่ปรากฏ แล้วจึงบันทึก ถ้า citation ไม่ครบ/ผิดพลาดหรือขนาดไม่อยู่ในช่วง "
        "จะปฏิเสธการบันทึกและรายงานเหตุผล ให้แจ้งเหตุผลตามจริงกลับไปยัง Content Manager"
    )
    args_schema: Type[BaseModel] = PublishInput

    def _run(self, content: str) -> str:
        sources = load_sources(SOURCES_PATH)
        report = analyze(
            content,
            sources,
            min_chars=ARTICLE_MIN_CHARS,
            max_chars=ARTICLE_MAX_CHARS,
            min_citations=CITATION_MIN_COUNT,
            require_in_sources=CITATION_REQUIRE_IN_SOURCES,
        )
        if not report.ok:
            return (
                f"[publish_article] ปฏิเสธการเผยแพร่ ไม่ได้บันทึก {FINAL_ARTICLE_FILE} "
                "กรุณารายงานเหตุผลด้านล่างให้ Content Manager เพื่อให้แก้ไขแล้วส่งบทความทั้งฉบับมาใหม่\n"
                + format_report(report, "ฉบับที่ส่งมาเผยแพร่")
            )

        new_text, mapping = renumber(content, sources)

        # ตรวจซ้ำหลังเรียงเลข ต้องผ่านและเลขต้องเรียง 1..k
        check = analyze(
            new_text,
            sources,
            min_chars=ARTICLE_MIN_CHARS,
            max_chars=ARTICLE_MAX_CHARS,
            min_citations=CITATION_MIN_COUNT,
            require_in_sources=CITATION_REQUIRE_IN_SOURCES,
        )
        if not (check.ok and check.order_ok and not check.unused_defined):
            return (
                "[publish_article] ปฏิเสธ: การเรียงเลข citation ใหม่ให้ผลที่ไม่สอดคล้อง ไม่ได้บันทึกไฟล์\n"
                + format_report(check, "หลังเรียงเลขใหม่")
            )

        target = BASE_DIR / FINAL_ARTICLE_FILE
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")
        except OSError as e:
            return f"[publish_article] เขียนไฟล์ไม่สำเร็จ: {e}"

        changed = {o: n for o, n in mapping.items() if o != n}
        if changed:
            remap = ", ".join(f"[{o}]→[{n}]" for o, n in sorted(changed.items()))
        else:
            remap = "ไม่มีการเปลี่ยนเลข (เรียงถูกต้องอยู่แล้ว)"
        dropped = report.unused_defined
        return (
            f"เผยแพร่สำเร็จ: {target}\n"
            f"- ขนาดเนื้อหา {check.body_chars} ตัวอักษร (กำหนด {ARTICLE_MIN_CHARS}-{ARTICLE_MAX_CHARS})\n"
            f"- citation ที่ใช้ได้จริง {len(check.valid)} แหล่ง (ขั้นต่ำ {CITATION_MIN_COUNT})\n"
            f"- การเรียงเลข citation ใหม่: {remap}\n"
            f"- รายการอ้างอิงที่ถูกตัดออกเพราะไม่ได้อ้างในเนื้อหา: "
            + (", ".join(f"[{i}]" for i in dropped) if dropped else "ไม่มี")
        )
