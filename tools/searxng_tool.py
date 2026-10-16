"""CrewAI tool สำหรับค้นหาข้อมูลผ่าน SearXNG (self-hosted)

หมายเหตุ: ต้องเปิด JSON output ใน SearXNG ก่อน โดยแก้ settings.yml
    search:
      formats:
        - html
        - json
"""
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config import (
    SEARXNG_LANGUAGE,
    SEARXNG_MAX_RESULTS,
    SEARXNG_TIMEOUT,
    SEARXNG_URL,
)


class SearxngSearchInput(BaseModel):
    query: str = Field(..., description="คำค้นหาที่ต้องการ (query string)")
    max_results: int = Field(SEARXNG_MAX_RESULTS, description="จำนวนผลลัพธ์สูงสุดที่ต้องการ (1-10)")


class SearxngSearchTool(BaseTool):
    name: str = "searxng_search"
    description: str = (
        "ค้นหาข้อมูลจากอินเทอร์เน็ตผ่าน SearXNG "
        "คืนค่าเป็นรายการผลลัพธ์ประกอบด้วย title, url และ snippet "
        "ใช้เมื่อต้องการข้อมูลอ้างอิงหรือข้อเท็จจริงล่าสุด"
    )
    args_schema: Type[BaseModel] = SearxngSearchInput

    def _run(self, query: str, max_results: int = SEARXNG_MAX_RESULTS) -> str:
        max_results = max(1, min(max_results, 10))
        try:
            params = {"q": query, "format": "json"}
            if SEARXNG_LANGUAGE:
                params["language"] = SEARXNG_LANGUAGE
            resp = requests.get(
                f"{SEARXNG_URL}/search",
                params=params,
                timeout=SEARXNG_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])[:max_results]
        except requests.RequestException as e:
            return f"[searxng_search] เรียก SearXNG ไม่สำเร็จ: {e}"
        except ValueError:
            return (
                "[searxng_search] response ไม่ใช่ JSON "
                "(ตรวจสอบว่าเปิด format json ใน settings.yml แล้ว)"
            )

        if not results:
            return f"ไม่พบผลลัพธ์สำหรับ: {query}"

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "(no title)")
            url = r.get("url", "")
            snippet = (r.get("content") or "").strip()
            lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
        return "\n\n".join(lines)
