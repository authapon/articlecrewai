# Article Crew

ทีม AI agent (CrewAI) สำหรับเขียนบทความตามหัวข้อที่กำหนด โดยค้นข้อมูลจากอินเทอร์เน็ตผ่าน **SearXNG**
ดึงและสกัดเนื้อหาจากเว็บ เขียนบทความพร้อม **citation** แล้วให้ผู้ตรวจ 2 บุคลิกช่วยตรวจและแนะนำการแก้ไข
ก่อนบันทึกเป็นไฟล์ ใช้ LLM จาก **LM Studio** (OpenAI API compatible)

## ภาพรวมการทำงาน

ใช้ `Process.hierarchical` มี **Content Manager** เป็นผู้รับงานเดียว (1 task) และ delegate ให้ทีม:

| Agent | หน้าที่ | Tools |
|---|---|---|
| **Content Manager** | รับงาน delegate ให้ทีม ตัดสินว่าผ่านหรือต้องแก้ (ไม่เกิน 2 รอบ) | — |
| **Research Specialist** | ค้นหาและคัดเลือกแหล่งข้อมูลที่น่าเชื่อถือ | `searxng_search` |
| **Web Content Extractor** | ดึงหน้าเว็บ สกัดข้อเท็จจริงพร้อมที่มา (รหัสแหล่ง [n], URL, วันที่เข้าถึง) แล้วบันทึกลง `sources.md` | `web_fetch`, `file_write` |
| **Content Writer** | อ่าน `sources.md` แล้วเขียนบทความพร้อม citation `[n]` และรายการอ้างอิง (ตอบเป็น Markdown ล้วน) | `file_read` |
| **Publisher** | บันทึกไฟล์ลงดิสก์ตามเนื้อหาที่ได้รับ | `file_write` |
| **Fact and Citation Auditor** | ผู้ตรวจบุคลิกสงสัย ตรวจข้อเท็จจริงและ citation เทียบกับแหล่งจริง | `file_read`, `web_fetch`, `searxng_search` |
| **Reader-Advocate Editor** | ผู้ตรวจบุคลิกตัวแทนผู้อ่าน ตรวจความชัดเจน โครงสร้าง น้ำเสียง | `file_read` |

ลำดับงาน: ค้นหา → ดึงและสกัดข้อมูล (บันทึก `sources.md`) → เขียน (อ่านจาก `sources.md`) → (บันทึก draft) + ตรวจโดยผู้ตรวจ 2 คน → แก้ไข → บันทึกฉบับสุดท้ายและรายงานผลตรวจ

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

ผลลัพธ์อยู่ในโฟลเดอร์ `output/` (เปลี่ยนได้ด้วย `ARTICLE_OUTPUT_DIR`):

```
output/
├── article.md          # บทความฉบับสุดท้าย (มี citation และแหล่งอ้างอิง)
├── sources.md          # source notes จาก Extractor (ที่ Writer และผู้ตรวจอ่านร่วมกัน)
├── review_report.md    # สรุปผลตรวจจากผู้ตรวจทั้งสอง
└── drafts/draft_1.md   # ฉบับร่างก่อนแก้ไข
```

## การตั้งค่า

ค่าทั้งหมดอ่านผ่าน `config.py` ลำดับความสำคัญคือ
**environment variable ของระบบ → ไฟล์ `.env` → ค่า default**
ค่าที่ไม่ตั้งหรือเว้นว่างไว้จะใช้ค่า default ส่วนค่าตัวเลข/boolean ที่ผิดรูปแบบจะแจ้งเตือนทาง stderr แล้วใช้ค่า default

ตัวอย่างการตั้งค่าครั้งเดียวผ่านเชลล์โดยไม่แก้ `.env`:

```bash
SEARXNG_URL=http://192.168.1.20:8080 CREW_MODEL=openai/qwen3-14b python main.py
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
| `MIN_ARTICLE_CHARS` | `500` | ความยาวขั้นต่ำของบทความที่ `file_write` ยอมบันทึก |
| `FILE_READ_MAX_CHARS` | `8000` | จำนวนตัวอักษรต่อการเรียก `file_read` หนึ่งครั้ง (สูงสุด 20000) ไฟล์ยาวอ่านต่อด้วย `offset` |
| **Crew / บทความ** | | |
| `CREW_VERBOSE` | `true` | แสดงขั้นตอนการทำงานของ agent |
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
└── tools/
    ├── searxng_tool.py        # ค้นหาผ่าน SearXNG
    ├── web_fetch_tool.py      # ดึงและสกัดเนื้อหาเว็บ
    ├── file_writer_tool.py    # เขียนไฟล์ + guard ตรวจบทความ
    └── file_reader_tool.py    # อ่านไฟล์ใน output (ให้ผู้ตรวจเปิดอ่านบทความ)
```

## กลไกความปลอดภัยและความถูกต้อง

- **`web_fetch`** รองรับเฉพาะ `http/https` ปฏิเสธ host ภายใน (localhost, IP ส่วนตัว) และตรวจซ้ำทุก redirect เพื่อกัน SSRF
  เพราะ URL มาจากผลค้นหาและ LLM นอกจากนี้ agent ที่อ่านเว็บถูกกำกับให้ถือเนื้อหาเว็บเป็นข้อมูลดิบ ไม่ทำตามคำสั่งในหน้าเว็บ
  (ลดความเสี่ยง prompt injection แต่ไม่ได้ป้องกันทั้งหมด)
- **`file_write`** เขียนได้เฉพาะภายใน `ARTICLE_OUTPUT_DIR` และนามสกุล `.md` `.txt` `.json`
  ไฟล์บทความ (`article*.md` และไฟล์ใน `drafts/`) จะถูกปฏิเสธถ้าสั้นกว่า `MIN_ARTICLE_CHARS`
  หรือไม่มีส่วน "แหล่งอ้างอิง" เพื่อจับกรณี LLM ส่งต่อเนื้อหาไม่ครบ
- **`file_read`** อ่านได้เฉพาะภายใน `ARTICLE_OUTPUT_DIR` และนามสกุล `.md` `.txt` `.json` (กัน path traversal)
  ผู้ตรวจทั้งสองใช้เปิดอ่านบทความจากไฟล์ตรง ๆ แทนข้อความที่ Manager พิมพ์ส่งต่อ ไฟล์ยาวอ่านทีละช่วงด้วย `offset`
  และใส่ `filename='.'` เพื่อดูรายชื่อไฟล์ได้
- **Shared workspace (`sources.md`)** Extractor บันทึก source notes ลงไฟล์ทันทีหลังดึงแต่ละแหล่ง (แหล่งแรก overwrite แหล่งถัดไป append)
  Writer อ่านจากไฟล์นี้ และ Auditor ใช้เทียบ citation กับ notes ตัวจริง แทนการให้ Manager พิมพ์ส่งต่อ
  ช่วยลด token ใน context ของ Manager และตัดปัญหาเนื้อหาเพี้ยนระหว่างส่งต่อ ไฟล์จะถูกเขียนทับทุกครั้งที่เริ่มรันใหม่
- ควรเปิดตรวจ citation สำคัญด้วยตัวเองก่อนเผยแพร่ เพราะผู้ตรวจเป็น LLM และตรวจได้แค่ตามที่ `web_fetch` ดึงมาได้
  (หน้าที่ต้อง login หรือโหลดด้วย JavaScript จะดึงเนื้อหาไม่ได้)

## แก้ปัญหาที่พบบ่อย

| อาการ | สาเหตุ/วิธีแก้ |
|---|---|
| `coworker mentioned not found` | ถ้ารายชื่อ coworker ในข้อความ error ไม่ครบ ตรวจว่า Task **ไม่ได้ระบุ `agent=`** (โหมด hierarchical) ถ้ารายชื่อครบแล้วแต่ยังเกิด แปลว่าโมเดลพิมพ์ชื่อ role ผิด ให้ใช้โมเดลที่ใหญ่ขึ้น |
| ค้นหาไม่ได้ / response ไม่ใช่ JSON / 403 | ยังไม่ได้เปิด `json` ใน `search.formats` ของ SearXNG หรือ `SEARXNG_URL` ไม่ถูกต้อง |
| Connection error ไปยัง LLM | ตรวจว่า LM Studio เปิด server แล้ว และ `LMSTUDIO_BASE_URL` ลงท้ายด้วย `/v1` |
| Model not found | `CREW_MODEL` ต้องตรงกับ id จาก `curl http://127.0.0.1:14900/v1/models` เช่น id `qwen/qwen3.5-4b` ให้ตั้ง `CREW_MODEL=openai/qwen/qwen3.5-4b` |
| context overflow / บทความถูกตัดกลางทาง | เพิ่ม context length ใน LM Studio (แนะนำ 16k ขึ้นไป) ตรวจ `CREW_MAX_TOKENS` และลด `WEB_FETCH_MAX_CHARS` |
| `file_write` ปฏิเสธการบันทึก | เนื้อหาที่ส่งต่อสั้นเกินไปหรือไม่มีแหล่งอ้างอิง (มักเกิดจากการย่อ/ตัดตอน) Manager จะถูกแจ้งให้ส่งบทความทั้งฉบับใหม่ |
| Manager ไม่ delegate / เรียก tool ผิดรูปแบบ | โมเดลเล็ก (เช่น 4B) ทำ tool calling และ delegation ซ้อนชั้นไม่เสถียร ลองโมเดลที่ใหญ่ขึ้นหรือหัวข้อที่ง่ายลงก่อน |

## ข้อควรรู้

โมเดลทุก agent ใช้ตัวเดียวกัน (`llm` ใน `main.py`) และบทความจะถูก Manager ส่งต่อโดยการพิมพ์ซ้ำ
จึงมีโอกาสที่เนื้อหาเพี้ยนจากต้นฉบับเมื่อใช้โมเดลเล็ก `file_write` guard ตรวจได้เฉพาะความยาวและส่วนอ้างอิง
ถ้าพบปัญหานี้บ่อย ให้พิจารณาบันทึก `result.raw` ลงไฟล์ในโค้ดหลัง `crew.kickoff()` แทนการให้ Publisher บันทึก
