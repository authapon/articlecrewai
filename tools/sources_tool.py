"""CrewAI tool สำหรับเพิ่มแหล่งข้อมูลลง sources.md

เลข ID ของแต่ละแหล่งถูกกำหนดโดย tool นี้ (ไม่ใช่ LLM) และ URL เดิมจะไม่ถูกเพิ่มซ้ำ
(ถ้าส่ง URL เดิมมาอีก ข้อมูลใหม่จะถูกเพิ่มเข้าแหล่งเดิม)
"""
from datetime import date
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from config import CITATION_MIN_COUNT, SOURCES_FILE
from tools.citations import Source, is_http_url, load_sources, normalize_url, save_sources
from tools.fs_utils import SOURCES_PATH

MAX_FACTS_PER_CALL = 10
MAX_FACT_CHARS = 600
MAX_QUOTE_CHARS = 300


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SourcesAddInput(BaseModel):
    url: str = Field(..., description="URL ของหน้าเว็บที่ดึงข้อมูลมา (ต้องเป็น URL ที่เปิดอ่านจริงด้วย web_fetch)")
    title: str = Field(..., description="ชื่อหน้า/ชื่อบทความของแหล่งข้อมูล")
    facts: list[str] = Field(..., description="ข้อเท็จจริง/ตัวเลขสำคัญที่มีในหน้านั้นจริง รายการละ 1 ประโยค (3-6 รายการ)")
    quotes: list[str] = Field(default_factory=list, description="คำพูดสั้น ๆ จากต้นฉบับที่ใช้ได้ (ไม่บังคับ)")

    @field_validator("facts", "quotes", mode="before")
    @classmethod
    def _to_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):  # โมเดลเล็กมักส่งเป็นข้อความเดียว
            return [x.strip(" -•\t") for x in v.splitlines() if x.strip(" -•\t")]
        return v


class SourcesAddTool(BaseTool):
    name: str = "sources_add"
    description: str = (
        f"บันทึกแหล่งข้อมูลพร้อมข้อเท็จจริง/คำพูดสั้น ๆ ลง {SOURCES_FILE} และคืนเลข [ID] ของแหล่งนั้น "
        "ใช้หลังดึงหน้าเว็บด้วย web_fetch เท่านั้น ห้ามบันทึกข้อมูลที่ไม่มีในหน้าเว็บ "
        "ID ถูกกำหนดโดยเครื่องมือและเป็นเลขที่ใช้อ้างอิงใน citation"
    )
    args_schema: Type[BaseModel] = SourcesAddInput

    def _run(self, url: str, title: str, facts: list[str], quotes: list[str] | None = None) -> str:
        url = url.strip()
        if not is_http_url(url):
            return "[sources_add] ปฏิเสธ: url ต้องเป็น http/https ที่ถูกต้อง"
        facts = [_clip(f, MAX_FACT_CHARS) for f in (facts or []) if f.strip()][:MAX_FACTS_PER_CALL]
        quotes = [_clip(q, MAX_QUOTE_CHARS) for q in (quotes or []) if q.strip()][:MAX_FACTS_PER_CALL]
        if not facts:
            return "[sources_add] ปฏิเสธ: ต้องมี facts อย่างน้อย 1 รายการ"

        try:
            sources = load_sources(SOURCES_PATH)
            existing = next((s for s in sources if normalize_url(s.url) == normalize_url(url)), None)
            if existing:
                existing.facts += [f for f in facts if f not in existing.facts]
                existing.quotes += [q for q in quotes if q not in existing.quotes]
                if not existing.title and title.strip():
                    existing.title = title.strip()
                source, action = existing, "เพิ่มข้อมูลในแหล่งเดิม (URL ซ้ำ ไม่สร้างแหล่งใหม่)"
            else:
                source = Source(
                    id=max((s.id for s in sources), default=0) + 1,
                    title=title.strip() or "(ไม่มีชื่อ)",
                    url=url,
                    accessed=date.today().isoformat(),
                    facts=facts,
                    quotes=quotes,
                )
                sources.append(source)
                action = "เพิ่มแหล่งใหม่"
            save_sources(SOURCES_PATH, sources)
        except OSError as e:
            return f"[sources_add] เขียนไฟล์ไม่สำเร็จ: {e}"

        return (
            f"บันทึกแล้ว: [{source.id}] {source.title} ({action}) | "
            f"{SOURCES_FILE} มีทั้งหมด {len(sources)} แหล่ง (บทความต้องมี citation ที่ใช้ได้จริงอย่างน้อย {CITATION_MIN_COUNT})"
        )
