# Article Crew

ทีม AI agent (CrewAI) สำหรับเขียนบทความตามหัวข้อที่กำหนด โดยค้นข้อมูลผ่าน **SearXNG** ดึงและสกัดเนื้อหาจากเว็บ
สะสมไว้ใน `sources.md` เขียนบทความพร้อม **citation** แล้วให้ผู้ตรวจ 2 บุคลิกตรวจและแนะนำการแก้ไข
บทความจะถูกเผยแพร่ก็ต่อเมื่อ **ขนาดและจำนวน citation ผ่านเกณฑ์ที่ตรวจด้วยโค้ด** เท่านั้น ใช้ LLM จาก **LM Studio** (OpenAI API compatible)

## ภาพรวมการทำงาน

ใช้ `Process.hierarchical` มี **Content Manager** เป็นผู้รับงานเดียว (1 task) และ delegate ให้ทีม:

| Agent | หน้าที่ | Tools |
|---|---|---|
| **Content Manager** | รับงาน delegate ให้ทีม ตัดสินตามกฎการอนุมัติ (ห้ามปล่อยงานที่ citation ไม่ผ่าน) | — |
| **Research Specialist** | ค้นหาและคัดเลือก URL ใหม่ที่ยังไม่อยู่ใน `sources.md` (ค้นเพิ่มตามคำแนะนำได้) | `searxng_search`, `file_read` |
| **Web Content Extractor** | ดึงหน้าเว็บ สกัดข้อเท็จจริง และเพิ่มลง `sources.md` (อ่านไฟล์เดิมก่อนเพื่อไม่ดึงซ้ำ) | `web_fetch`, `sources_add`, `file_read` |
| **Content Writer** | เขียน/แก้บทความจาก `sources.md` พร้อม citation (ตอบเป็น Markdown ล้วน ไม่บันทึกไฟล์) | `file_read` (อ่านอย่างเดียว) |
| **Publisher** | บันทึกฉบับร่าง รายงานผลตรวจ และเผยแพร่ฉบับสุดท้าย (เรียงเลข citation ใหม่ให้) | `file_write`, `publish_article` |
| **Fact and Citation Auditor** | ผู้ตรวจบุคลิกสงสัย: ตรวจข้อเท็จจริงเทียบแหล่ง และรายงานจำนวน citation ที่ใช้ได้จริงจาก `article_check` | `article_check`, `file_read`, `web_fetch`, `searxng_search` |
| **Reader-Advocate Editor** | ผู้ตรวจบุคลิกตัวแทนผู้อ่าน: ตรวจความชัดเจน/โครงสร้าง และเสนอคำค้นให้ไปหาข้อมูลเพิ่ม (`SEARCH_SUGGESTIONS`) | `file_read` |

### ลำดับงาน

1. **Research Specialist** ค้นหา URL → **Web Content Extractor** ดึงแล้วบันทึกลง `sources.md` ด้วย `sources_add`
2. **Content Writer** อ่าน `sources.md` แล้วเขียนบทความ → **Publisher** บันทึกเป็น `drafts/draft_N.md`
3. ผู้ตรวจทั้งสองอ่านไฟล์ draft: Auditor รายงาน `CITATION_VERDICT` / `SIZE_VERDICT`, Reader-Advocate รายงาน `CONTENT_VERDICT` และ `SEARCH_SUGGESTIONS`
4. ถ้าต้องแก้: Research Specialist และ Extractor ค้นเพิ่มตามคำแนะนำลง `sources.md` → Writer แก้ตาม feedback ทั้งสองชุดและใช้ข้อมูลใหม่ → Publisher บันทึก draft ถัดไป → ตรวจซ้ำ
5. เมื่อผ่านเงื่อนไข Publisher เรียก `publish_article` ซึ่งตรวจซ้ำ **เรียงเลข citation ใหม่ตามลำดับที่ปรากฏ** แล้วบันทึก `article.md` (ถ้า citation ไม่ครบ/ผิดพลาด จะปฏิเสธและแจ้ง Manager)

### กฎการอนุมัติของ Content Manager

"รอบ" คือจำนวนครั้งที่ Writer แก้ไขฉบับร่างหลังได้รับ feedback

- **ห้ามเผยแพร่บทความที่ citation ผิดพลาดหรือไม่ครบ** ตัดสินจากผลเครื่องมือ ไม่ใช่การประเมินของ LLM
- citation หรือขนาดยังไม่ผ่าน: แก้ต่อได้ไม่เกิน `CITATION_MAX_FIX_ROUNDS` รอบ ถ้าครบแล้วยังไม่ผ่าน **จะไม่เผยแพร่** (สถานะ `NOT_PUBLISHED` พร้อมเหตุผลใน `review_report.md`)
- citation ผ่านแล้วแต่เนื้อหายังมีประเด็น: ปรับแก้ได้ไม่เกิน `REVISION_MAX_ROUNDS` รอบ (ค่าเริ่มต้น 3) ถ้าครบแล้วอนุโลมให้เผยแพร่ โดยบันทึกประเด็นที่เหลือไว้ใน `review_report.md`

### การรับประกันด้วยโค้ด (ไม่พึ่ง LLM)

LLM นับตัวอักษรและนับ citation เองไม่แม่น จึงมี tool ที่ใช้ตรรกะใน `tools/citations.py`:

- **`article_check`** (Auditor) นับขนาดเนื้อหา, citation ที่ใช้ได้จริง, citation ที่ไม่มีนิยาม/ใช้ไม่ได้ แล้วสรุป `CITATION_VERDICT` และ `SIZE_VERDICT`
- **`publish_article`** (Publisher) เป็นทางเดียวที่เขียน `article.md` ได้ และจะ **ปฏิเสธการบันทึก** ถ้าขนาดไม่อยู่ในช่วง, citation ไม่ถึงขั้นต่ำ, อ้างแหล่งที่ไม่อยู่ใน `sources.md` หรือมี citation ที่ไม่มีนิยาม ต่อให้ Manager ทำผิดกฎ บทความที่ citation ไม่ผ่านก็ไม่หลุดออกมา
- **`sources_add`** กำหนดเลข ID ของแต่ละแหล่งเอง และไม่เพิ่ม URL ซ้ำ ทำให้ LLM แต่งแหล่งอ้างอิงขึ้นมาเองไม่ได้ (URL ที่อ้างต้องเคยถูกบันทึกจากหน้าที่ดึงจริง)

**นิยาม "citation ที่ใช้ได้จริง"** คือแหล่งที่ (1) ไม่ซ้ำกัน (URL เดียวกันนับเป็น 1) (2) ถูกอ้างในเนื้อหาด้วย `[n]` (3) มี URL ถูกต้องในรายการอ้างอิง และ (4) URL นั้นมีอยู่ใน `sources.md` (ปิดได้ด้วย `CITATION_REQUIRE_IN_SOURCES=false`) รูปแบบที่รองรับคือ `[1]`, `[1][2]` และ `[1, 2]` (ไม่รองรับ `[1-3]`)

**นิยามขนาดบทความ** นับเฉพาะเนื้อหา ไม่รวมส่วน "แหล่งอ้างอิง" และไม่นับช่องว่าง/ขึ้นบรรทัดใหม่ นับเป็น Unicode code point ดังนั้นสระและวรรณยุกต์ภาษาไทยนับเป็น 1 ตัวอักษรด้วย

## ข้อกำหนดเบื้องต้น

- Python 3.10+ (ทดสอบโครงสร้างกับ crewai 1.15.x)
- **LM Studio** เปิด local server และโหลดโมเดลไว้แล้ว (ค่า default: `http://127.0.0.1:14900/v1`, โมเดล `qwen3.5-4b`)
- **SearXNG** ที่เข้าถึงได้ (ค่า default: `http://127.0.0.1:3001`) และต้องเปิด JSON output ใน `settings.yml`:

  ```yaml
  search:
    formats:
      - html
      - json
  ```

## การติดตั้ง

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # แก้เฉพาะค่าที่ต้องการเปลี่ยน (ไม่บังคับ)
```

## การรัน

```bash
python main.py                          # ใช้หัวข้อจาก ARTICLE_TOPIC (หรือค่า default)
python main.py "หัวข้อบทความที่ต้องการ"   # ระบุหัวข้อผ่านอาร์กิวเมนต์ (มีผลเหนือ ARTICLE_TOPIC)
```

ทุกครั้งที่เริ่มรอบใหม่ ผลลัพธ์รอบก่อนจะถูกย้ายไป `output/archive/<เวลา>/` และ `sources.md` จะเริ่มใหม่ว่างเปล่า
(เพื่อไม่ให้แหล่งข้อมูลของหัวข้อเก่ามาปนและทำให้การตรวจ citation ผ่านโดยผิดพลาด) ปิดการเก็บถาวรได้ด้วย `ARCHIVE_PREVIOUS_RUN=false` (จะลบทิ้งแทน)

ผลลัพธ์อยู่ในโฟลเดอร์ `output/` (เปลี่ยนได้ด้วย `ARTICLE_OUTPUT_DIR`):

```
output/
├── article.md          # บทความฉบับสุดท้าย (มีเฉพาะเมื่อผ่านเกณฑ์ citation และขนาด)
├── review_report.md    # สรุปผลตรวจ จำนวนรอบ และประเด็นที่เหลือ
├── sources.md          # แหล่งข้อมูลที่สะสม พร้อมข้อเท็จจริงและเลข [ID]
├── drafts/draft_N.md   # ฉบับร่างแต่ละรอบ
└── archive/            # ผลลัพธ์ของรอบก่อน ๆ
```

## การตั้งค่า

ค่าทั้งหมดอ่านผ่าน `config.py` ลำดับความสำคัญคือ
**environment variable ของระบบ → ไฟล์ `.env` → ค่า default**
ค่าที่ไม่ตั้งหรือเว้นว่างไว้จะใช้ค่า default ส่วนค่าตัวเลข/boolean ที่ผิดรูปแบบจะแจ้งเตือนทาง stderr แล้วใช้ค่า default
ค่าที่ขัดกันเอง (เช่น `ARTICLE_MIN_CHARS` มากกว่า `ARTICLE_MAX_CHARS`) จะหยุดโปรแกรมพร้อมข้อความอธิบาย

ตัวอย่างการตั้งค่าครั้งเดียวผ่านเชลล์โดยไม่แก้ `.env`:

```bash
ARTICLE_MIN_CHARS=2000 ARTICLE_MAX_CHARS=5000 CITATION_MIN_COUNT=4 python main.py "หัวข้อ"
```

| ตัวแปร | Default | คำอธิบาย |
|---|---|---|
| **LLM** | | |
| `CREW_MODEL` | `openai/qwen3.5-4b` | `openai/` + id โมเดลตามที่ `GET /v1/models` รายงาน |
| `LMSTUDIO_BASE_URL` | `http://127.0.0.1:14900/v1` | ต้องลงท้ายด้วย `/v1` |
| `LMSTUDIO_API_KEY` | `lm-studio` | LM Studio ไม่ตรวจ แต่ต้องมีค่า |
| `CREW_TEMPERATURE` | `0.3` | |
| `CREW_MAX_TOKENS` | `8192` | จำนวน token สูงสุดต่อการตอบ |
| **SearXNG** | | |
| `SEARXNG_URL` | `http://127.0.0.1:3001` | |
| `SEARXNG_TIMEOUT` | `20` | วินาที |
| `SEARXNG_MAX_RESULTS` | `5` | จำนวนผลลัพธ์ต่อการค้นหา (สูงสุด 10) |
| `SEARXNG_LANGUAGE` | *(ว่าง)* | เช่น `th`, `en`, `auto`; ว่าง = ไม่ส่งพารามิเตอร์ |
| **Web fetch** | | |
| `WEB_FETCH_TIMEOUT` | `20` | วินาที |
| `WEB_FETCH_MAX_BYTES` | `2000000` | ขนาดสูงสุดที่ดาวน์โหลดต่อหน้า |
| `WEB_FETCH_MAX_CHARS` | `6000` | จำนวนตัวอักษรของเนื้อหาที่ส่งให้ LLM ต่อหน้า (สูงสุด 20000) |
| `WEB_FETCH_MAX_REDIRECTS` | `3` | |
| `WEB_FETCH_USER_AGENT` | `Mozilla/5.0 (compatible; ArticleCrewBot/1.0)` | |
| `ALLOW_PRIVATE_FETCH` | `false` | อนุญาตดึงจาก localhost/เครือข่ายภายใน |
| **ไฟล์ผลลัพธ์** | | |
| `ARTICLE_OUTPUT_DIR` | `output` | path แบบ relative อิงจากโฟลเดอร์โปรเจกต์ |
| `SOURCES_FILE` | `sources.md` | ชื่อไฟล์สะสมแหล่งข้อมูล |
| `ARCHIVE_PREVIOUS_RUN` | `true` | ย้ายผลลัพธ์รอบก่อนไป `archive/` (false = ลบทิ้ง) |
| `FILE_READ_MAX_CHARS` | `8000` | จำนวนตัวอักษรสูงสุดต่อการอ่านไฟล์ 1 ครั้ง (อ่านต่อด้วย `offset`) |
| **ข้อกำหนดของบทความ** | | |
| `ARTICLE_MIN_CHARS` | `3000` | ความยาวเนื้อหาขั้นต่ำ (ตัวอักษร) |
| `ARTICLE_MAX_CHARS` | `8000` | ความยาวเนื้อหาสูงสุด (ตัวอักษร) |
| `CITATION_MIN_COUNT` | `5` | จำนวน citation ที่ใช้ได้จริงขั้นต่ำ (นับเป็นแหล่งที่ไม่ซ้ำกัน) |
| `CITATION_REQUIRE_IN_SOURCES` | `true` | URL ที่อ้างต้องเคยถูกบันทึกใน `sources.md` |
| `REVISION_MAX_ROUNDS` | `3` | citation ผ่านแล้ว แก้เนื้อหาได้อีกไม่เกินกี่รอบ ครบแล้วอนุโลมให้เผยแพร่ |
| `CITATION_MAX_FIX_ROUNDS` | `6` | citation/ขนาดยังไม่ผ่าน แก้ได้ไม่เกินกี่รอบ ครบแล้วไม่เผยแพร่ (ถ้าน้อยกว่า `REVISION_MAX_ROUNDS` จะถูกปรับให้เท่ากัน) |
| **Crew / บทความ** | | |
| `CREW_VERBOSE` | `true` | แสดงขั้นตอนการทำงานของ agent |
| `MANAGER_MAX_ITER` | `60` | จำนวนรอบการคิด/เรียก tool สูงสุดของ Manager (delegate หลายครั้ง จึงต้องสูง) |
| `AGENT_MAX_ITER` | `30` | จำนวนรอบสูงสุดของ agent อื่น |
| `ARTICLE_TOPIC` | `แนวโน้ม Local LLM สำหรับงาน Edge AI` | |
| `ARTICLE_AUDIENCE` | `นักศึกษาและนักพัฒนาซอฟต์แวร์` | |
| `ARTICLE_LANGUAGE` | `ภาษาไทย (ศัพท์เทคนิคใช้ภาษาอังกฤษได้)` | ภาษาของบทความ |
| `OTEL_SDK_DISABLED` | *(ไม่ตั้ง)* | ตั้งเป็น `true` เพื่อปิด telemetry ของ CrewAI (ไม่บังคับ) |

## โครงสร้างโปรเจกต์

```
article_crew/
├── main.py                    # นิยาม agents, task, crew และจุดเริ่มรัน
├── config.py                  # โหลด .env และอ่านค่าตั้งทั้งหมด
├── .env.example               # ตัวอย่างไฟล์ตั้งค่า
├── requirements.txt
├── tools/
│   ├── citations.py           # ตรรกะตรวจ/เรียงเลข citation และอ่านเขียน sources.md (ไม่พึ่ง crewai)
│   ├── searxng_tool.py        # ค้นหาผ่าน SearXNG
│   ├── web_fetch_tool.py      # ดึงและสกัดเนื้อหาเว็บ
│   ├── sources_tool.py        # sources_add: เพิ่มแหล่งลง sources.md
│   ├── file_reader_tool.py    # file_read: อ่านไฟล์ใน output (read-only)
│   ├── file_writer_tool.py    # file_write: ฉบับร่าง/รายงาน (กัน sources.md และ article.md)
│   ├── article_check_tool.py  # article_check: นับขนาด/citation
│   ├── publish_tool.py        # publish_article: ตรวจ + เรียงเลข citation + บันทึก article.md
│   └── fs_utils.py            # จำกัด path ให้อยู่ใน output
└── tests/
    └── test_citations.py      # unit test ของตรรกะ citation/sources/publish
```

ทดสอบตรรกะที่ไม่เกี่ยวกับ LLM ได้ด้วย `python -m unittest discover -s tests -v` (ใช้โฟลเดอร์ชั่วคราว ไม่ยุ่งกับ `output/` จริง)

## กลไกความปลอดภัย

- **`web_fetch`** รองรับเฉพาะ `http/https` ปฏิเสธ host ภายใน (localhost, IP ส่วนตัว) และตรวจซ้ำทุก redirect เพื่อกัน SSRF
  เพราะ URL มาจากผลค้นหาและ LLM agent ที่อ่านเว็บถูกกำกับให้ถือเนื้อหาเว็บเป็นข้อมูลดิบ ไม่ทำตามคำสั่งในหน้าเว็บ
  (ลดความเสี่ยง prompt injection แต่ไม่ได้ป้องกันทั้งหมด)
- ทุก tool ไฟล์เข้าถึงได้เฉพาะภายใน `ARTICLE_OUTPUT_DIR` และนามสกุล `.md` `.txt` `.json`
- `sources.md` เขียนได้ผ่าน `sources_add` เท่านั้น และ `article.md` เขียนได้ผ่าน `publish_article` เท่านั้น

## ข้อจำกัดที่ควรรู้

- **การตรวจ citation ด้วยโค้ดยืนยันได้แค่โครงสร้าง** (ครบ ไม่ซ้ำ ไม่มีนิยามขาด URL มาจากหน้าที่ดึงจริง) ไม่ได้ยืนยันว่า
  ข้อความตรงกับเนื้อหาในแหล่ง ส่วนนี้ยังพึ่ง Auditor (LLM) และเว็บที่ต้อง login หรือโหลดด้วย JavaScript ดึงเนื้อหาไม่ได้
  ควรเปิดตรวจ citation สำคัญด้วยตัวเองก่อนเผยแพร่
- บทความถูก Manager พิมพ์ส่งต่อให้ Publisher ใหม่ จึงมีโอกาสเนื้อหาเพี้ยนจากที่ Writer เขียนเมื่อใช้โมเดลเล็ก
  (ตัวตรวจจับกรณี citation หาย/ขนาดผิด/แหล่งปลอม แต่ไม่รู้ถ้าถ้อยคำถูกแก้เล็กน้อย)
- งานนี้ใช้การ delegate ซ้อนหลายชั้นและวนแก้หลายรอบ ใช้ context และเวลามาก โมเดลขนาดเล็ก (เช่น 4B) ทำ tool calling และ
  delegation ได้ไม่เสถียร ถ้า Manager วนไม่จบ ให้ลดข้อกำหนด (`CITATION_MIN_COUNT`, `ARTICLE_*_CHARS`) หรือใช้โมเดลที่ใหญ่ขึ้น

## แก้ปัญหาที่พบบ่อย

| อาการ | สาเหตุ/วิธีแก้ |
|---|---|
| `coworker mentioned not found` | ถ้ารายชื่อ coworker ในข้อความ error ไม่ครบ ตรวจว่า Task **ไม่ได้ระบุ `agent=`** (โหมด hierarchical) ถ้ารายชื่อครบแล้วแต่ยังเกิด แปลว่าโมเดลพิมพ์ชื่อ role ผิด ให้ใช้โมเดลที่ใหญ่ขึ้น |
| ค้นหาไม่ได้ / response ไม่ใช่ JSON / 403 | ยังไม่ได้เปิด `json` ใน `search.formats` ของ SearXNG หรือ `SEARXNG_URL` ไม่ถูกต้อง |
| Connection error ไปยัง LLM | ตรวจว่า LM Studio เปิด server แล้ว และ `LMSTUDIO_BASE_URL` ลงท้ายด้วย `/v1` |
| Model not found | `CREW_MODEL` ต้องตรงกับ id จาก `curl http://127.0.0.1:14900/v1/models` เช่น id `qwen/qwen3.5-4b` ให้ตั้ง `CREW_MODEL=openai/qwen/qwen3.5-4b` |
| context overflow / บทความถูกตัดกลางทาง | เพิ่ม context length ใน LM Studio (แนะนำ 16k ขึ้นไป) ตรวจ `CREW_MAX_TOKENS` ลด `WEB_FETCH_MAX_CHARS` และลด `ARTICLE_MAX_CHARS` |
| ไม่มี `article.md` และสถานะ `NOT_PUBLISHED` | citation หรือขนาดไม่ผ่านจนครบ `CITATION_MAX_FIX_ROUNDS` ดูเหตุผลใน `review_report.md` และผลของ `article_check` ใน `drafts/` |
| `publish_article` ปฏิเสธ | อ่านเหตุผลใน output: citation ไม่ถึงขั้นต่ำ, URL ไม่อยู่ใน `sources.md`, citation ไม่มีนิยาม หรือขนาดไม่อยู่ในช่วง |
| `file_write` ปฏิเสธฉบับร่าง | เนื้อหาสั้นเกินไปหรือไม่มีหัวข้อ 'แหล่งอ้างอิง' (มักเกิดจากการย่อ/ตัดตอน) Manager จะถูกแจ้งให้ส่งบทความทั้งฉบับใหม่ |
| Manager หยุดเร็วเกินไป / "max iterations" | เพิ่ม `MANAGER_MAX_ITER` |
| Manager ไม่ delegate / เรียก tool ผิดรูปแบบ | โมเดลเล็กทำ tool calling และ delegation ซ้อนชั้นไม่เสถียร ลองโมเดลที่ใหญ่ขึ้นหรือหัวข้อที่ง่ายลงก่อน |
