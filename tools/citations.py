"""ตรรกะแบบ deterministic สำหรับตรวจ/จัดเรียง citation และอ่าน-เขียน sources.md

แยกออกมาโดยไม่พึ่ง crewai เพื่อให้ทดสอบง่าย และเพราะ LLM นับตัวอักษร/นับ citation เองไม่น่าเชื่อถือ
agent จึงต้องเรียก tool ที่ใช้โมดูลนี้ (article_check, publish_article, sources_add) แทนการนับเอง

รูปแบบบทความที่โมดูลนี้เข้าใจ:
  - อ้างในเนื้อหาด้วย [n] หรือ [n, m]   (ไม่รองรับ [1-3])
  - ท้ายบทความมีหัวข้อ "แหล่งอ้างอิง" (หรือ References) ตามด้วยรายการ
        [n] ชื่อเรื่อง. https://url. เข้าถึงเมื่อ YYYY-MM-DD
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>)\]\"']+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\](?!\()")
REF_ENTRY_RE = re.compile(r"^\s*(?:[-*+]\s*)?\[(\d{1,3})\]\s*[:.)\-]?\s*(.+?)\s*$")
REF_HEADINGS = {"แหล่งอ้างอิง", "เอกสารอ้างอิง", "references", "reference", "sources", "bibliography"}
SOURCE_HEAD_RE = re.compile(r"(?m)^## \[(\d+)\]\s*(.*)$")


# ======================================================================
# URL
# ======================================================================
def normalize_url(url: str) -> str:
    """ทำให้ URL เปรียบเทียบกันได้: ตัด fragment, ตัด / ท้าย path, lowercase scheme/host"""
    url = url.strip().rstrip(".,;")
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.query, ""))


def is_http_url(url: str) -> bool:
    p = urlsplit(url.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


# ======================================================================
# sources.md
# ======================================================================
@dataclass
class Source:
    id: int
    title: str
    url: str
    accessed: str = ""
    facts: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)


def _field(block: str, name: str) -> str:
    m = re.search(rf"(?m)^- {name}:[ \t]*(.*)$", block)
    return m.group(1).strip() if m else ""


def _bullets(block: str, name: str) -> list[str]:
    items: list[str] = []
    active = False
    for line in block.splitlines():
        if line.strip() == f"- {name}:":
            active = True
            continue
        if not active:
            continue
        if line.startswith("  - "):
            items.append(line[4:].strip())
        elif line.startswith("- "):
            break
    return items


def load_sources(path: Path) -> list[Source]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    heads = list(SOURCE_HEAD_RE.finditer(text))
    sources: list[Source] = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[m.end():end]
        quotes = [q.strip().strip('"').strip() for q in _bullets(block, "Quotes")]
        sources.append(
            Source(
                id=int(m.group(1)),
                title=m.group(2).strip(),
                url=_field(block, "URL"),
                accessed=_field(block, "Accessed"),
                facts=_bullets(block, "Facts"),
                quotes=[q for q in quotes if q],
            )
        )
    return sources


def render_sources(sources: list[Source]) -> str:
    out = [
        "# Sources",
        "",
        "> ไฟล์นี้ถูกจัดการโดยเครื่องมือ sources_add ห้ามแก้เลข ID เอง "
        "(ใช้ [ID] ในวงเล็บเหลี่ยมนี้เป็นเลข citation ตอนร่างบทความ)",
        "",
    ]
    for s in sources:
        out.append(f"## [{s.id}] {' '.join(s.title.split())}")
        out.append(f"- URL: {s.url}")
        out.append(f"- Accessed: {s.accessed}")
        out.append("- Facts:")
        out.extend(f"  - {' '.join(f.split())}" for f in s.facts)
        out.append("- Quotes:")
        out.extend(f'  - "{" ".join(q.split())}"' for q in s.quotes)
        out.append("")
    return "\n".join(out)


def save_sources(path: Path, sources: list[Source]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(render_sources(sources), encoding="utf-8")
    tmp.replace(path)  # atomic


# ======================================================================
# Article parsing
# ======================================================================
@dataclass
class Ref:
    id: int
    title: str
    url: str
    accessed: str


@dataclass
class Parsed:
    body: str
    refs: list[Ref]
    header_line: str | None
    dup_ids: list[int]


def parse_article(text: str) -> Parsed:
    lines = text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        label = re.sub(r"^[#*\s]+|[*:\s]+$", "", line).lower()
        if label in REF_HEADINGS:
            idx = i  # ใช้หัวข้อสุดท้ายที่พบ
    if idx is None:
        return Parsed(body=text, refs=[], header_line=None, dup_ids=[])

    refs: list[Ref] = []
    seen: set[int] = set()
    dup_ids: list[int] = []
    for line in lines[idx + 1:]:
        m = REF_ENTRY_RE.match(line)
        if not m:
            continue
        rid, rest = int(m.group(1)), m.group(2)
        um = URL_RE.search(rest)
        url = um.group(0).rstrip(".,;") if um else ""
        title = rest[: um.start()] if um else rest
        title = re.sub(r"\]\($", "", title.strip()).lstrip("[")
        title = re.sub(r"[\s.\-–|:(\[]+$", "", title).strip()
        dm = DATE_RE.search(rest)
        if rid in seen:
            dup_ids.append(rid)
            continue
        seen.add(rid)
        refs.append(Ref(rid, title, url, dm.group(0) if dm else ""))
    return Parsed(body="\n".join(lines[:idx]), refs=refs, header_line=lines[idx], dup_ids=dup_ids)


def count_body_chars(body: str) -> int:
    """นับตัวอักษรของเนื้อหา โดยไม่นับช่องว่าง/ขึ้นบรรทัดใหม่ (นับเป็น Unicode code point)"""
    return len(re.sub(r"\s+", "", body))


def used_citations(body: str) -> list[int]:
    """เลข citation ที่อ้างในเนื้อหา เรียงตามลำดับที่ปรากฏครั้งแรก (ไม่ซ้ำ)"""
    order: list[int] = []
    for m in CITE_RE.finditer(body):
        for n in re.split(r"\s*,\s*", m.group(1)):
            if int(n) not in order:
                order.append(int(n))
    return order


# ======================================================================
# Analysis
# ======================================================================
@dataclass
class Report:
    body_chars: int
    min_chars: int
    max_chars: int
    min_citations: int
    has_refs: bool
    used: list[int]
    defined: list[int]
    undefined_used: list[int]
    unused_defined: list[int]
    valid: dict[int, str]  # id -> url (เฉพาะที่นับเป็นแหล่งที่ใช้ได้จริง ไม่ซ้ำกัน)
    invalid: list[tuple[int, str]]
    duplicates: list[tuple[int, int]]  # (id ที่ซ้ำ, id ที่ถูกนับแล้ว)
    dup_ids: list[int]
    order_ok: bool
    id_mismatch: list[str]

    @property
    def size_ok(self) -> bool:
        return self.min_chars <= self.body_chars <= self.max_chars

    @property
    def citations_ok(self) -> bool:
        return (
            self.has_refs
            and not self.undefined_used
            and not self.invalid
            and not self.dup_ids
            and len(self.valid) >= self.min_citations
        )

    @property
    def ok(self) -> bool:
        return self.size_ok and self.citations_ok


def analyze(
    text: str,
    sources: list[Source],
    *,
    min_chars: int,
    max_chars: int,
    min_citations: int,
    require_in_sources: bool = True,
) -> Report:
    parsed = parse_article(text)
    used = used_citations(parsed.body)
    refs = {r.id: r for r in parsed.refs}
    src_by_url = {normalize_url(s.url): s for s in sources if s.url}

    undefined = [n for n in used if n not in refs]
    unused = [r.id for r in parsed.refs if r.id not in used]

    valid: dict[int, str] = {}
    seen_urls: dict[str, int] = {}
    invalid: list[tuple[int, str]] = []
    duplicates: list[tuple[int, int]] = []
    mismatch: list[str] = []
    for n in used:
        r = refs.get(n)
        if r is None:
            continue
        if not r.url or not is_http_url(r.url):
            invalid.append((n, "รายการอ้างอิงไม่มี URL ที่ถูกต้อง (http/https)"))
            continue
        nu = normalize_url(r.url)
        if require_in_sources and nu not in src_by_url:
            invalid.append((n, f"URL ไม่อยู่ใน sources.md (ไม่เคยถูกดึง/บันทึกผ่าน sources_add): {r.url}"))
            continue
        if nu in seen_urls:
            duplicates.append((n, seen_urls[nu]))
            continue
        seen_urls[nu] = n
        valid[n] = r.url
        s = src_by_url.get(nu)
        if s is not None and s.id != n:
            mismatch.append(f"[{n}] ในบทความคือแหล่งที่เป็น [{s.id}] ใน sources.md")

    return Report(
        body_chars=count_body_chars(parsed.body),
        min_chars=min_chars,
        max_chars=max_chars,
        min_citations=min_citations,
        has_refs=parsed.header_line is not None and bool(parsed.refs),
        used=used,
        defined=[r.id for r in parsed.refs],
        undefined_used=undefined,
        unused_defined=unused,
        valid=valid,
        invalid=invalid,
        duplicates=duplicates,
        dup_ids=parsed.dup_ids,
        order_ok=used == list(range(1, len(used) + 1)),
        id_mismatch=mismatch,
    )


def _fmt_ids(ids) -> str:
    return ", ".join(f"[{i}]" for i in ids) if ids else "-"


def format_report(rep: Report, label: str) -> str:
    if rep.body_chars < rep.min_chars:
        size_note = f"ขาดอีก {rep.min_chars - rep.body_chars} ตัวอักษร"
    elif rep.body_chars > rep.max_chars:
        size_note = f"เกินมา {rep.body_chars - rep.max_chars} ตัวอักษร"
    else:
        size_note = "อยู่ในช่วงที่กำหนด"
    missing = max(0, rep.min_citations - len(rep.valid))

    lines = [
        f"ARTICLE_CHECK: {label}",
        f"- ขนาดเนื้อหา (ไม่รวมแหล่งอ้างอิง ไม่นับช่องว่าง): {rep.body_chars} ตัวอักษร "
        f"(กำหนด {rep.min_chars}-{rep.max_chars}) → {size_note}",
        f"- มีส่วน 'แหล่งอ้างอิง' พร้อมรายการ: {'ใช่' if rep.has_refs else 'ไม่ใช่'}",
        f"- citation ที่อ้างในเนื้อหา (ไม่ซ้ำเลข): {len(rep.used)} รายการ: {_fmt_ids(rep.used)}",
        f"- citation ที่ใช้ได้จริง (ไม่ซ้ำแหล่ง): {len(rep.valid)} จากขั้นต่ำ {rep.min_citations}"
        + (f" → ขาดอีก {missing} แหล่ง" if missing else " → ครบ"),
    ]
    if rep.undefined_used:
        lines.append(f"- อ้างในเนื้อหาแต่ไม่มีในรายการอ้างอิง: {_fmt_ids(rep.undefined_used)}")
    for n, why in rep.invalid:
        lines.append(f"- citation [{n}] ใช้ไม่ได้: {why}")
    for n, first in rep.duplicates:
        lines.append(f"- [{n}] เป็นแหล่งเดียวกับ [{first}] (นับเป็น 1 แหล่ง)")
    if rep.dup_ids:
        lines.append(f"- เลขในรายการอ้างอิงซ้ำกัน: {_fmt_ids(rep.dup_ids)}")
    if rep.unused_defined:
        lines.append(f"- อยู่ในรายการอ้างอิงแต่ไม่ได้อ้างในเนื้อหา (จะถูกตัดออกตอนเผยแพร่): {_fmt_ids(rep.unused_defined)}")
    if not rep.order_ok and rep.used:
        lines.append("- ลำดับเลข citation ไม่เรียงตามที่ปรากฏ (Publisher จะเรียงใหม่ให้ตอนเผยแพร่)")
    lines.extend(f"- หมายเหตุ: {m}" for m in rep.id_mismatch)
    lines.append(f"CITATION_VERDICT: {'PASS' if rep.citations_ok else 'FAIL'}")
    lines.append(f"SIZE_VERDICT: {'PASS' if rep.size_ok else 'FAIL'}")
    return "\n".join(lines)


# ======================================================================
# Renumbering
# ======================================================================
def renumber(text: str, sources: list[Source]) -> tuple[str, dict[int, int]]:
    """เรียงเลข citation ใหม่เป็น 1..k ตามลำดับที่ปรากฏในเนื้อหา และสร้างรายการอ้างอิงใหม่

    - แหล่งเดียวกัน (URL เดียวกัน) ที่ถูกอ้างด้วยหลายเลข จะรวมเป็นเลขเดียว
    - รายการอ้างอิงที่ไม่ได้ถูกอ้างในเนื้อหาจะถูกตัดออก
    เรียกใช้เฉพาะเมื่อ analyze() ผ่านแล้ว (ไม่มี citation ที่ไม่ได้นิยาม)
    คืนค่า (ข้อความใหม่, mapping เลขเก่า→เลขใหม่)
    """
    parsed = parse_article(text)
    refs = {r.id: r for r in parsed.refs}
    src_by_url = {normalize_url(s.url): s for s in sources if s.url}

    mapping: dict[int, int] = {}
    url_to_new: dict[str, int] = {}
    new_entries: list[tuple[int, Ref]] = []
    for old in used_citations(parsed.body):
        ref = refs[old]
        nu = normalize_url(ref.url)
        if nu not in url_to_new:
            url_to_new[nu] = len(url_to_new) + 1
            new_entries.append((url_to_new[nu], ref))
        mapping[old] = url_to_new[nu]

    def _sub(m: re.Match) -> str:
        nums = sorted({mapping[int(x)] for x in re.split(r"\s*,\s*", m.group(1))})
        return "[" + ", ".join(str(n) for n in nums) + "]"

    body = CITE_RE.sub(_sub, parsed.body).rstrip()

    entry_lines = []
    for new_id, ref in new_entries:
        src = src_by_url.get(normalize_url(ref.url))
        title = (ref.title or (src.title if src else "") or "(ไม่มีชื่อ)").rstrip(". ")
        accessed = ref.accessed or (src.accessed if src else "")
        line = f"[{new_id}] {title}. {ref.url}."
        if accessed:
            line += f" เข้าถึงเมื่อ {accessed}"
        entry_lines.append(line)

    new_text = f"{body}\n\n{parsed.header_line}\n\n" + "\n".join(entry_lines) + "\n"
    return new_text, mapping
