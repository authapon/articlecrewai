"""ทดสอบตรรกะ deterministic ของ citation / sources / publish

รัน:  python -m unittest discover -s tests -v   (จากโฟลเดอร์โปรเจกต์)
การทดสอบใช้โฟลเดอร์ output ชั่วคราวและค่าขนาดเล็ก ไม่ยุ่งกับ output จริง
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ต้องตั้งค่าก่อน import config/tools (config อ่านค่าตอน import)
_TMP = tempfile.mkdtemp(prefix="article_crew_test_")
os.environ.update(
    {
        "ARTICLE_OUTPUT_DIR": _TMP,
        "ARTICLE_MIN_CHARS": "100",
        "ARTICLE_MAX_CHARS": "400",
        "CITATION_MIN_COUNT": "3",
        "FILE_READ_MAX_CHARS": "50",
    }
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import citations as c  # noqa: E402
from tools.article_check_tool import ArticleCheckTool  # noqa: E402
from tools.file_reader_tool import FileReadTool  # noqa: E402
from tools.file_writer_tool import FileWriteTool  # noqa: E402
from tools.fs_utils import BASE_DIR, SOURCES_PATH  # noqa: E402
from tools.publish_tool import PublishArticleTool  # noqa: E402
from tools.sources_tool import SourcesAddInput, SourcesAddTool  # noqa: E402

URLS = {i: f"https://example.org/p{i}" for i in range(1, 7)}


def add_sources(n=5):
    t = SourcesAddTool()
    for i in range(1, n + 1):
        t._run(URLS[i], f"แหล่งที่ {i}", [f"ข้อเท็จจริง {i}"])


def make_article(body_len=150, cites=(1, 2, 3), refs=None, header="## แหล่งอ้างอิง"):
    """สร้างบทความ: ย่อหน้าละ 1 citation ตามลำดับที่ให้มา"""
    per = max(1, body_len // max(1, len(cites)))
    body = "\n\n".join("ก" * per + f"[{n}]" for n in cites)
    refs = cites if refs is None else refs
    ref_lines = "\n".join(f"[{n}] แหล่งที่ {n}. {URLS[n]}. เข้าถึงเมื่อ 2026-10-16" for n in refs)
    return f"# หัวข้อ\n\n{body}\n\n{header}\n\n{ref_lines}\n"


def reset():
    for p in BASE_DIR.rglob("*"):
        if p.is_file():
            p.unlink()


def analyze(text):
    return c.analyze(
        text, c.load_sources(SOURCES_PATH), min_chars=100, max_chars=400, min_citations=3
    )


class SourcesTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_ids_assigned_by_tool_and_url_deduped(self):
        t = SourcesAddTool()
        self.assertIn("[1]", t._run(URLS[1], "A", ["f1"]))
        self.assertIn("[2]", t._run(URLS[2], "B", ["f2"]))
        msg = t._run(URLS[1] + "/", "A again", ["f1b"])  # URL เดิม (ต่างแค่ / ท้าย)
        self.assertIn("[1]", msg)
        self.assertIn("เดิม", msg)
        srcs = c.load_sources(SOURCES_PATH)
        self.assertEqual([s.id for s in srcs], [1, 2])
        self.assertEqual(srcs[0].facts, ["f1", "f1b"])

    def test_rejects_bad_url_and_empty_facts(self):
        t = SourcesAddTool()
        self.assertIn("ปฏิเสธ", t._run("ftp://x.org/a", "A", ["f"]))
        self.assertIn("ปฏิเสธ", t._run(URLS[1], "A", []))

    def test_string_facts_are_split(self):
        out = SourcesAddInput.model_validate(
            {"url": URLS[1], "title": "A", "facts": "- ข้อ 1\n- ข้อ 2"}
        )
        self.assertEqual(out.facts, ["ข้อ 1", "ข้อ 2"])


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        reset()
        add_sources(5)

    def test_pass(self):
        r = analyze(make_article())
        self.assertTrue(r.ok, c.format_report(r, "x"))
        self.assertEqual(len(r.valid), 3)

    def test_too_few_citations(self):
        r = analyze(make_article(cites=(1, 2)))
        self.assertFalse(r.citations_ok)
        self.assertIn("ขาดอีก 1 แหล่ง", c.format_report(r, "x"))

    def test_citation_not_in_sources_is_invalid(self):
        t = make_article(cites=(1, 2, 6))  # URLS[6] ไม่เคยถูกบันทึก
        r = analyze(t)
        self.assertFalse(r.citations_ok)
        self.assertEqual([n for n, _ in r.invalid], [6])

    def test_undefined_and_unused(self):
        r = analyze(make_article(cites=(1, 2, 3, 4), refs=(1, 2, 3, 5)))
        self.assertEqual(r.undefined_used, [4])
        self.assertEqual(r.unused_defined, [5])
        self.assertFalse(r.citations_ok)

    def test_duplicate_url_counts_once(self):
        text = make_article(cites=(1, 2, 3)).replace(URLS[3], URLS[2])
        r = analyze(text)
        self.assertEqual(len(r.valid), 2)
        self.assertEqual(r.duplicates, [(3, 2)])
        self.assertFalse(r.citations_ok)

    def test_missing_references_section(self):
        text = make_article().split("## แหล่งอ้างอิง")[0]
        r = analyze(text)
        self.assertFalse(r.has_refs)
        self.assertFalse(r.citations_ok)

    def test_size_limits(self):
        self.assertFalse(analyze(make_article(body_len=30)).size_ok)
        self.assertFalse(analyze(make_article(body_len=2000)).size_ok)
        self.assertTrue(analyze(make_article(body_len=150)).size_ok)

    def test_char_count_excludes_whitespace_and_references(self):
        parsed = c.parse_article("ก ข\nค\n\n## แหล่งอ้างอิง\n[1] t. https://example.org/p1.")
        self.assertEqual(c.count_body_chars(parsed.body), 3)

    def test_comma_lists_are_recognised(self):
        self.assertEqual(c.used_citations("ข้อความ[2, 1] และ [3] [2]"), [2, 1, 3])
        self.assertEqual(c.used_citations("[link](https://x.org) ไม่ใช่ citation"), [])


class RenumberAndPublishTests(unittest.TestCase):
    def setUp(self):
        reset()
        add_sources(5)

    def test_renumber_by_first_appearance(self):
        text = make_article(cites=(4, 2, 5))
        new, mapping = c.renumber(text, c.load_sources(SOURCES_PATH))
        self.assertEqual(mapping, {4: 1, 2: 2, 5: 3})
        r = analyze(new)
        self.assertEqual(r.used, [1, 2, 3])
        self.assertTrue(r.order_ok)
        self.assertEqual(r.unused_defined, [])
        self.assertIn(f"[1] แหล่งที่ 4. {URLS[4]}.", new)  # รายการอ้างอิงตามเลขใหม่

    def test_renumber_rewrites_comma_groups_and_drops_unused(self):
        body = "ก" * 50 + "[5, 2]" + "ข" * 50 + "[2]" + "ค" * 50 + "[4]"
        refs = "\n".join(f"[{n}] แหล่งที่ {n}. {URLS[n]}." for n in (1, 2, 4, 5))
        text = f"{body}\n\n## แหล่งอ้างอิง\n\n{refs}\n"
        new, mapping = c.renumber(text, c.load_sources(SOURCES_PATH))
        self.assertEqual(mapping, {5: 1, 2: 2, 4: 3})
        self.assertIn("[1, 2]", new)  # [5, 2] → [1, 2]
        self.assertNotIn(URLS[1], new)  # [1] ไม่ได้ถูกอ้าง จึงถูกตัดออก

    def test_publish_renumbers_and_saves(self):
        out = PublishArticleTool()._run(make_article(cites=(4, 2, 5)))
        self.assertIn("เผยแพร่สำเร็จ", out)
        self.assertIn("[4]→[1]", out)
        saved = (BASE_DIR / "article.md").read_text(encoding="utf-8")
        self.assertTrue(analyze(saved).ok)
        self.assertEqual(analyze(saved).used, [1, 2, 3])

    def test_publish_refuses_when_citations_insufficient(self):
        out = PublishArticleTool()._run(make_article(cites=(1, 2)))
        self.assertIn("ปฏิเสธ", out)
        self.assertIn("CITATION_VERDICT: FAIL", out)
        self.assertFalse((BASE_DIR / "article.md").exists())

    def test_publish_refuses_fabricated_source(self):
        out = PublishArticleTool()._run(make_article(cites=(1, 2, 6)))
        self.assertIn("ไม่อยู่ใน sources.md", out)
        self.assertFalse((BASE_DIR / "article.md").exists())

    def test_publish_refuses_wrong_size(self):
        out = PublishArticleTool()._run(make_article(body_len=2000))
        self.assertIn("SIZE_VERDICT: FAIL", out)
        self.assertFalse((BASE_DIR / "article.md").exists())


class FileToolTests(unittest.TestCase):
    def setUp(self):
        reset()
        add_sources(5)

    def test_write_blocks_sources_and_final_article(self):
        w = FileWriteTool()
        self.assertIn("sources_add", w._run("sources.md", "x" * 600))
        self.assertIn("publish_article", w._run("article.md", make_article()))
        self.assertFalse((BASE_DIR / "article.md").exists())

    def test_write_draft_guard_and_ok(self):
        w = FileWriteTool()
        self.assertIn("ปฏิเสธ", w._run("drafts/draft_1.md", "(เนื้อหาบทความ)"))
        self.assertIn("ปฏิเสธ", w._run("drafts/draft_1.md", make_article().split("## แหล่ง")[0] * 3))
        self.assertIn("บันทึกสำเร็จ", w._run("drafts/draft_1.md", make_article()))
        self.assertIn("บันทึกสำเร็จ", w._run("review_report.md", "สรุปผลตรวจสั้น ๆ"))

    def test_write_blocks_traversal_and_bad_ext(self):
        w = FileWriteTool()
        self.assertIn("ปฏิเสธ", w._run("../evil.md", "x"))
        self.assertIn("ปฏิเสธ", w._run("a.py", "x"))

    def test_read_paging_and_traversal(self):
        r = FileReadTool()
        first = r._run("sources.md")
        self.assertIn("ยังมีต่อ", first)
        self.assertIn("offset=50", first)
        self.assertIn("ปฏิเสธ", r._run("../x.md"))
        self.assertIn("ไม่พบไฟล์", r._run("nope.md"))

    def test_article_check_tool(self):
        FileWriteTool()._run("drafts/draft_1.md", make_article())
        out = ArticleCheckTool()._run("drafts/draft_1.md")
        self.assertIn("CITATION_VERDICT: PASS", out)
        self.assertIn("SIZE_VERDICT: PASS", out)
        FileWriteTool()._run("drafts/draft_2.md", make_article(cites=(1, 2)))
        self.assertIn("CITATION_VERDICT: FAIL", ArticleCheckTool()._run("drafts/draft_2.md"))
        self.assertIn("ไม่พบไฟล์", ArticleCheckTool()._run("drafts/none.md"))


if __name__ == "__main__":
    unittest.main()
