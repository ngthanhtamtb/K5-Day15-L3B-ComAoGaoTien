# Kiến trúc backend ScriptGuard — bản đề xuất để duyệt

> Trạng thái: **v2, đang làm** trong `backend/eduguard-backend/backend/` (28/11). Đã làm và có test: GĐ 0, 1, 2, phần chính GĐ 3, 4, 5a; chi tiết và phần còn thiếu ở `EDUGUARD.md`. Còn mở: bản quyền code nguồn (§10), voice API thật (GĐ 5b).
> Phạm vi: thư mục `backend/` mới trong repo này. **Không đụng** `codebase/`, `eval/`, `run.py`. Đây là phần bài nộp hackathon: bộ chạy eval và hợp đồng `answer(text)` phải giữ nguyên.

## 0. Tóm tắt

Gộp 3 nguồn thành một backend Python (FastAPI):

| Nguồn | Lấy gì | Bỏ / thay gì |
|---|---|---|
| **RAGslides-be** (FastAPI, Gemini) | Toàn bộ tính năng: auth/users, presentations (trang, bình luận, chia sẻ, quyền, cộng tác, hoạt động), templates (bộ sưu tập, duyệt, tương tác, thống kê, báo cáo), AI (dàn ý, sinh slide stream, cải thiện / dịch nội dung, làm giàu slide, sinh ảnh), media, token tracker, analytics; engine `pptagent` (map JSON slide của AI vào template, tự co chữ); 4 template + 140 layout mẫu + font | Bỏ bước gửi tài liệu sang server ngoài `124.158.5.35` → thay bằng module xử lý tài liệu tự viết (§3). Bỏ việc nhồi cả tài liệu vào prompt → thay bằng truy xuất đoạn có mã nguồn. Endpoint export đang rỗng → làm thật. Chỉ có Gemini → thêm lớp provider |
| **BE_Zentus / ai-service** (Python worker) | Trích PDF (pdfplumber + PyMuPDF, OCR theo trang bằng model nhìn ảnh khi trang ít chữ), DOCX, PPTX; `pages.json` có cấu trúc (trang, heading, mục, điều khoản); chọn ngữ cảnh theo trọng tâm; tách ảnh PDF kèm vị trí và đoạn chữ gần nhất; sinh quiz 7 loại (mc, ms, tf, fill, short, match, flashcard) × 3 mức khó, giải thích từng phương án, `sourceEvidence`; kiểm grounding; chuẩn hoá output; gọi LLM có fallback nhiều key | Bỏ Kafka, MinIO bắt buộc, quiz-service Node → thay bằng job nền trong tiến trình và kho file có interface (local mặc định, MinIO tuỳ chọn) |
| **Repo này** (`codebase/`, prototype ScriptGuard) | Bộ gắn nhãn KHOP / SAI / THIEU / TU_CHOI, tách chỉ dẫn chèn, 2 cổng duyệt, trace token / chi phí, xuất PDF quiz, mã đoạn `Dxx-Syy`, 6 màn của prototype | Không bỏ gì. `codebase/` giữ nguyên cho eval; backend gọi lại logic này qua module `verification` |

Phần **mới hoàn toàn**: xử lý tài liệu lấy được cả ảnh, bảng, bố cục; kịch bản thuyết trình chia theo đoạn giọng đọc; voice (API bạn đưa sau); quiz có chiều sâu; slide kèm giọng đọc.

## 1. Luồng chính (bám prototype)

```
Tải tài liệu (PDF/DOCX/PPTX/MD/TXT)
   │  ingest job: trích chữ + bảng + ảnh + bố cục → DocumentModel → đoạn có mã (Dxx-Syy / -Tnn / -Inn)
   ▼
Kho tài liệu theo buổi  ─────────────────────────────────────────────┐
   │                                                                 │
   ├─► [Màn 1] Dán kịch bản có sẵn ──┐                               │
   └─► Sinh kịch bản từ tài liệu ────┤ (dàn ý → slide → lời đọc      │
                                     │  chia đoạn A1..An, mỗi đoạn   │ truy xuất
                                     ▼  gắn mã đoạn)                 │ đoạn nguồn
               [Màn 2] CỔNG 1 — rà soát kịch bản: KHOP/SAI/THIEU/TU_CHOI ◄┘
                    giảng viên chấp nhận / từ chối / sửa từng câu
                                     │
            ┌────────────────────────┴───────────────────────┐
            ▼                                                ▼
 [Màn 3] Tạo slide: số slide, 16:9/4:3,            Quiz: loại câu, mức khó,
  mẫu, kèm ghi chú người nói, kèm quiz              số câu, từ kịch bản hoặc tài liệu
  → map vào template (pptagent)                     → sinh + grounding + kiểm từng phương án
  → ảnh / bảng lấy từ tài liệu gốc                  → gắn ảnh từ tài liệu
  → TTS từng đoạn A1..An                            → PDF đề + PDF đáp án
            ▼                                                ▼
 [Màn 4] CỔNG 2 — kiểm từng slide:                 [Màn 5] CỔNG 2 — kiểm từng câu:
  ý + đoạn giọng đọc có nhãn và nguồn               đề, A–D, đáp án, giải thích có nhãn
  sửa 1 đoạn → kiểm lại + TTS lại đoạn đó           sửa → kiểm lại, đề xuất sửa kèm nguồn
            └──────────────────────┬─────────────────────────┘
                                   ▼
                    Gửi chờ duyệt (status = cho_duyet). KHÔNG có endpoint xuất bản.
 [Panel Agent verify] mọi bước trả trace: các bước đã chạy, số lần gọi model, token, chi phí, lỗi
```

## 2. Cấu trúc thư mục

```
backend/
├── ARCHITECTURE.md            (file này)
├── pyproject.toml / requirements.txt
├── alembic/ , alembic.ini     migration (từ RAGslides-be)
├── main.py                    FastAPI app, mount /api/v1, /static, /ui
├── app/
│   ├── core/                  config, database, auth, response, exceptions, enums  (RAGslides-be)
│   │   ├── llm/               registry nhiều provider + định tuyến theo việc (§7.1)
│   │   │                      (gộp pptagent/llm_client + Zentus llm._call_*)
│   │   ├── billing/           ★ khung gói & quyền tính năng (§7.2) — chưa thu tiền, chưa chặn thật
│   │   ├── pptagent/          slide_processor, schemas, types, filters  (RAGslides-be, sửa nhỏ)
│   │   ├── storage/           interface FileStore: LocalStore (mặc định) | MinioStore (Zentus)
│   │   ├── jobs/              hàng đợi job nền trong tiến trình + bảng jobs + tiến độ qua SSE
│   │   └── tracing/           trace từng bước (tương thích panel Agent verify)
│   ├── documents/             ★ MỚI — xử lý tài liệu (§3)
│   │   ├── extract/           pdf.py, docx.py, pptx.py, text.py, ocr.py (vision), caption.py (mô tả ảnh)
│   │   ├── model.py           DocumentModel / Page / Block
│   │   ├── segmenter.py       Block → đoạn có mã Dxx-Snn / Dxx-Tnn / Dxx-Inn
│   │   └── index.py           tìm kiếm lai: BM25 + heading + (tuỳ chọn) embedding
│   ├── verification/          ★ gắn nhãn KHOP/SAI/THIEU/TU_CHOI, tách chỉ dẫn chèn, đề xuất sửa,
│   │                          kiểm từng phương án quiz  (port từ codebase/agent.py + Zentus grounding)
│   ├── scripts/               ★ kịch bản: sinh từ tài liệu, rà soát, quyết định, gửi chờ duyệt
│   ├── slides/                outline, slides, content, enrichment, images  (RAGslides services/ai)
│   ├── quiz/                  ★ generator, prompt_builder, parser, grounding, depth (Zentus + mới)
│   ├── voice/                 ★ TTSProvider (adapter, theo job), cache, chia đoạn theo giới hạn,
│   │                          hàng đợi có giới hạn tốc độ, ước tính chi phí, ghép timeline A1..An (§4.1)
│   ├── exports/               PPTX (kèm ghi chú người nói), PDF slide, PDF quiz đề/đáp án, HTML có audio
│   ├── presentations/ templates/ users/ media/ analytics/   (RAGslides services, giữ nguyên tính năng)
│   ├── models/                SQLAlchemy: bảng của RAGslides + documents, segments, assets, scripts,
│   │                          script_claims, quizzes, questions, voice_clips, jobs, review_decisions
│   ├── schemas/               Pydantic
│   └── api/v1/endpoints/      (§6)
├── data/                      templates/*.json, images/templates, image_pages (140 layout), fonts
└── tests/                     test cũ của Zentus (extractor, grounding, parser, prompt) + test mới
```

## 3. Xử lý tài liệu: lấy được chữ, bảng, ảnh và bố cục

Cả hai repo gốc đều yếu ở phần này: RAGslides không tự xử lý; Zentus đưa bảng DOCX xuống cuối (mất thứ tự), chỉ lấy ảnh PDF nằm gần "Câu N", không lấy bảng trong PDF, không lấy ảnh trong DOCX/PPTX.

**Mô hình chung** (mở rộng `pages.json` của Zentus):

```
Document { document_id, buoi, title, source_file, updated_date, pages[] }
Page     { page_number, width, height, image_render_ref, blocks[] }
Block    { block_id, type: heading|paragraph|list|table|image|caption|notes,
           text, bbox{x0,y0,x1,y1}, heading_path[], order,
           table?: { rows[[cell]], markdown, header_row },
           image?: { asset_id, w, h, ext, caption, ocr_text, nearest_text } }
```

| Định dạng | Chữ + thứ tự | Bảng | Ảnh | Bố cục |
|---|---|---|---|---|
| PDF | PyMuPDF `get_text("dict")` theo block, giữ bbox; trang < 40 ký tự → OCR bằng model nhìn ảnh (Zentus) | PyMuPDF `page.find_tables()`, dự phòng pdfplumber `extract_tables()` → ô + markdown | `get_images` + `get_image_rects` (Zentus `media.py`, bỏ điều kiện phải gần "Câu N"); lọc ảnh nhỏ / trùng hash | bbox từng block, render trang PNG để UI tô sáng đoạn nguồn |
| DOCX | Duyệt `document.body` **theo đúng thứ tự** đoạn ↔ bảng (sửa lỗi Zentus); heading theo style | `docx.table` → ô, gộp ô | Ảnh inline qua relationship `r:embed` → blob | Thứ tự + cấp heading |
| PPTX | python-pptx theo shape, tiêu đề, **ghi chú người nói** | `shape.has_table` | `shape.shape_type == PICTURE` → `image.blob` | Vị trí shape, layout name → có thể dùng làm template mới |
| MD/TXT | Như `codebase/ingest.py` hiện tại | Bảng markdown | — | Heading `#` |

- **Ảnh dùng được cho tra cứu:** mỗi ảnh có `caption` do model nhìn ảnh mô tả (tuỳ chọn, cache theo hash) và `nearest_text`, nên câu hỏi kiểu "sơ đồ RAG gồm mấy bước" vẫn tìm được ảnh.
- **Mã đoạn tương thích repo hiện tại:** chữ `D01-S07`, bảng `D01-T02`, ảnh `D01-I03`. `data/sources/segments.json` vẫn đọc được, nên eval cũ không gãy.
- **Tra cứu:** BM25 (thư viện chuẩn) + điểm khớp heading (như `tools.py` hiện tại) + `select_structured_context` của Zentus; embedding là tuỳ chọn ở giai đoạn sau.

## 4. Kịch bản, slide và voice

**Kịch bản** (màn 1–2), có 2 đường vào:
1. Giảng viên dán bản nháp → tách câu → `verification` gắn nhãn từng câu → cổng 1.
2. Sinh từ tài liệu: dàn ý (RAGslides `outline`) → mỗi slide có tiêu đề, ≤4 ý, **lời thuyết trình chia đoạn A1..An**. Mỗi đoạn là 1–2 câu và gắn một mã đoạn nguồn → tự rà soát → cổng 1.

**Slide** (màn 3–4):
- Bỏ phần nhồi tài liệu vào prompt của RAGslides. Prompt mới nhận kịch bản đã duyệt cùng các đoạn nguồn, và bắt mỗi `item` mang `segment_id`.
- Loại slide: giữ `cover / contents / transition / content / end`, thêm `table` (bảng lấy từ tài liệu), `image_text` (ảnh gốc + ý), `comparison`, `process` (theo bộ layout `image_pages`), `quiz_end`.
- `slide_processor` của RAGslides map JSON vào template (giữ cơ chế co chữ theo khung). Ảnh ưu tiên lấy từ tài liệu gốc (có nguồn); chỉ sinh ảnh bằng AI cho slide bìa, và ảnh sinh ghi rõ "ảnh minh hoạ, không phải nguồn".
- Tuỳ chọn trên màn 3: số slide, 16:9 / 4:3, mẫu (AI20K chuẩn / Tối giản → map sang `template_id`), kèm ghi chú người nói, kèm quiz 5 câu.
- `speaker_notes` = lời thuyết trình.

**Hiển thị và sửa slide: làm cả hai** (quyết định 4):
- Định dạng chuẩn là **JSON phần tử kiểu PPTist** (shape / text / image / table / line có toạ độ; đã dùng trong template RAGslides). Mọi slide chỉ lưu một dạng này.
- **Đường 1, xem và duyệt:** bộ vẽ HTML/SVG thuần trong `ui/`, chỉ đọc JSON. Dùng cho màn 4 (mỗi ý có nhãn, nguồn, đoạn giọng đọc). Không cần build step.
- **Đường 2, sửa tự do:** trình sửa kiểu PPTist (frontend riêng, làm sau). Backend cấp sẵn `GET/PUT /presentations/{id}/pages/{n}` (đã có trong RAGslides), kiểm schema phần tử khi lưu. Mỗi lần lưu, những phần tử chữ có `segment_id` bị đổi nội dung sẽ **tự kiểm lại** (cổng 2).
- Mỗi phần tử chữ mang thêm `meta: {segment_id, claim_index, nhan}` để hai đường cùng hiện nhãn.

### 4.1 Voice (quyết định 5: API theo job, chưa rõ có mốc thời gian)

**Adapter** (thêm API thật = thêm một file, khai báo trong config):

```python
class TTSProvider(Protocol):
    name: str
    async def list_voices(self) -> list[Voice]                 # danh sách giọng: bạn cung cấp sau → registry trong config
    async def submit(self, text: str, voice: str, speed: float) -> str          # trả provider_job_id
    async def poll(self, provider_job_id: str) -> TTSJobStatus  # pending | done(audio_url|bytes, duration_s?, timings?) | failed
    limits: TTSLimits                                           # max_chars_per_request, rpm, concurrent_jobs, max_queue
    pricing: TTSPricing                                         # đơn vị tính (ký tự / giây audio / request), giá mỗi đơn vị
```

Provider có sẵn khi dev: `FakeTTS` (WAV im lặng, thời lượng ước theo số chữ) và `EdgeTTS` (bọc thành job giả).

**Luồng theo job:**
1. Kịch bản đã qua cổng 1. Mỗi slide có các đoạn A1..An.
2. Mỗi đoạn tạo một `voice_clip` (`hash(text, voice, speed, provider)` → cache: trùng thì dùng lại, không tốn tiền).
3. Worker gửi `submit`, rồi `poll` với backoff (1s → 2s → 4s…, tối đa N lần). Nếu API có webhook thì thêm endpoint nhận callback sau.
4. Xong → lưu audio vào FileStore, đo **thời lượng thật từ file** (đọc header WAV/MP3), cập nhật tiến độ job qua SSE.
5. Sửa một đoạn ở cổng 2 → chỉ đoạn đó bị huỷ cache và gửi lại.

**Mốc thời gian, khi API không trả:**
- Mốc **đoạn**: ghép thời lượng thật của từng file A1, A2… → 0:00, 0:11, 0:24 (đúng như prototype). Cách này chính xác, vì mỗi đoạn là một file riêng.
- Mốc **câu trong đoạn** (để tô sáng khi phát): chia thời lượng đoạn theo tỉ lệ số âm tiết của từng câu, cộng khoảng nghỉ ở dấu câu. Đánh dấu `timing_source: "uoc_tinh"`.
- Nếu API có trả mốc từng từ / câu thì dùng luôn, `timing_source: "provider"`.
- Kịch bản đề xuất là nguồn sự thật: audio sinh **từ đúng câu chữ đã duyệt**, không để TTS tự chia câu.

**Giới hạn và giá: cách xử lý trong code** (số cụ thể điền khi có API, xem `backend/config/tts.yaml`):

| Ràng buộc | Cách áp dụng |
|---|---|
| Giới hạn ký tự mỗi request | Đoạn dài hơn `max_chars_per_request` → cắt ở ranh giới câu (không cắt giữa câu), gửi nhiều request, ghép audio, cộng thời lượng |
| Số request / phút, số job đồng thời | Hàng đợi chung có token bucket (`rpm`) + semaphore (`concurrent_jobs`); gặp 429 → lùi theo `Retry-After` hoặc backoff có jitter |
| Lỗi tạm thời | Thử lại tối đa 3 lần; đoạn lỗi được đánh dấu, slide vẫn dựng được và hiện rõ "đoạn A2 thiếu audio" (như code hiện tại) |
| Giá | `chi_phi = so_don_vi × gia_moi_don_vi`. **Ước tính trước khi sinh** (hiện cho giảng viên: "~6.000 ký tự ≈ X đ"), ghi chi phí thật sau khi xong vào `token_tracker` / analytics, gộp chung panel Agent verify |
| Ngân sách | Mỗi gói có hạn mức ký tự / tháng (§7.2). Giai đoạn đầu **chỉ ghi nhận và cảnh báo**, không chặn |
| Tiết kiệm | Cache theo hash; nghe thử một đoạn trước khi sinh cả bài; chỉ sinh lại đoạn bị sửa |

**Ước lượng khối lượng để tính giá** *(tự ước tính, kiểm lại khi có số thật)*: 1 bài ≈ 10 slide × 3 đoạn × ~200 ký tự ≈ **6.000 ký tự**; sinh lại ~20% vì sửa → ~7.200 ký tự/bài. Quy mô cơ sở 8 người × 6 bài/tháng ≈ **~350.000 ký tự/tháng**. Nhân với đơn giá của API là ra chi phí voice/tháng; con số này cộng vào `cost/cost-estimate.md`.

**Xuất:** HTML có player theo từng đoạn (đã có), PPTX kèm ghi chú người nói (python-pptx không nhúng audio ổn định). Video MP4 (slide + audio bằng ffmpeg) để giai đoạn sau.

## 5. Quiz có chiều sâu

Nền là bộ sinh của Zentus: 7 loại câu, phân bố mức dễ / trung bình / khó, giải thích bắt buộc nói vì sao từng phương án sai, `sourceEvidence` trích nguyên văn, grounding kiểm token và trọng tâm, gắn ảnh từ tài liệu theo độ khớp chữ. Thêm các phần sau:

| Thêm | Cách làm |
|---|---|
| Cấp độ nhận thức | Bloom 6 cấp (nhớ, hiểu, vận dụng, phân tích, đánh giá, sáng tạo) map vào easy / medium / hard; mỗi câu có trường `bloom` |
| Câu nhiều bước | Câu `analysis` cần ≥2 đoạn nguồn (vd: nối tham số chunk với chất lượng truy xuất); lưu `segment_ids[]` |
| Câu tình huống | Đề có bối cảnh ("Một nhóm thấy model trả lời lan man…") rồi hỏi cách xử lý; đáp án vẫn phải có nguồn |
| Phương án nhiễu có chủ đích | Mỗi phương án sai ghi `misconception` (đảo chiều nhân quả, nhầm khái niệm, sai số liệu) để giải thích dạy được |
| Dùng bảng / ảnh | Câu đọc bảng (`D01-T02`), câu dựa trên hình (`D07-I01`) |
| Kiểm từng phương án | `verification` kiểm **cả 4 phương án** với nguồn, bắt câu có 2 đáp án đúng (ca B15 trong eval) |
| Xuất | PDF đề + PDF đáp án (`codebase/exporters.py`), JSON tương thích quiz-service của Zentus |

## 6. API (tiền tố `/api/v1`)

| Nhóm | Endpoint chính | Nguồn |
|---|---|---|
| auth, users | đăng ký, đăng nhập, refresh, hồ sơ | RAGslides |
| documents | `POST /documents` (upload → job) · `GET /documents/{id}` (trạng thái, trang) · `/pages/{n}` (ảnh trang + block) · `/segments` · `/assets/{id}` | mới |
| kho | `GET /kho` (buổi, ngày cập nhật, có bản cũ) | repo này |
| scripts | `POST /scripts` (dán hoặc `from_document`) · `/decisions` · `/accept-matching` · `/submit` | repo này + mới |
| slides / ai | `/ai/outline` (stream) · `/ai/slides` (SSE) · `/ai/improve` · `/ai/translate` · `/ai/images` | RAGslides |
| presentations | CRUD, pages, comments, sharing, permissions, collaboration, activity · `/gate1` · `/build` · `/gate2` · `/submit` | RAGslides + repo này |
| templates | CRUD, collections, approval, interactions, analytics, reports | RAGslides |
| quizzes | `POST /quizzes` (từ tài liệu / kịch bản / chủ đề) · gate1 · build · gate2 · submit · tải PDF | Zentus + repo này |
| voice | `GET /voice/voices` · `POST /voice/estimate` (ký tự, chi phí dự kiến) · `POST /voice/jobs` (cả bài hoặc danh sách đoạn) · `GET /voice/jobs/{id}` · `GET /voice/clips/{id}` · `POST /voice/clips/{id}/regenerate` | mới |
| billing (khung) | `GET /plans` · `GET /me/plan` (gói, quyền tính năng, hạn mức đã dùng) · `PUT /admin/users/{id}/plan` (admin gán tay) | mới |
| exports | `/exports/{presentation_id}?fmt=pptx|pdf|html` · `/exports/quiz/{id}?fmt=pdf|json` | làm thật |
| jobs | `GET /jobs/{id}` · `GET /jobs/{id}/events` (SSE) | mới |
| analytics | token, chi phí, trace | RAGslides + repo này |

Giữ một lớp tương thích `/api/scripts`, `/api/drafts`… để `ui/` hiện tại chạy được trong lúc chuyển đổi.

## 7. Dữ liệu và hạ tầng

- **DB (quyết định 2):** SQLAlchemy 2 + Alembic. **SQLite để test** (`sqlite:///backend/storage/dev.db`), đổi sang Postgres chỉ bằng `DATABASE_URL`. Để chạy được trên cả hai:
  - Không dùng kiểu riêng của Postgres trong model (RAGslides đang dùng `postgresql.UUID` / `JSONB`): đổi sang `sqlalchemy.Uuid`, `sqlalchemy.JSON`.
  - Migration Alembic dùng `render_as_batch=True` (SQLite cần khi đổi cột).
  - CI chạy test trên SQLite; có thêm một lệnh chạy test trên Postgres qua docker-compose.
- **File:** `LocalStore` (thư mục `backend/storage/`, nằm trong `.gitignore`), MinIO tuỳ chọn.
- **Job nền:** asyncio worker trong tiến trình + bảng `jobs` + SSE báo tiến độ. Dùng chung cho ingest, sinh slide, voice. Không dùng Kafka; cần mở rộng thì chuyển sang Redis / RQ sau.
- **Không gửi tài liệu tới server lạ.** OCR / mô tả ảnh chỉ gọi provider đã cấu hình, có cờ tắt.

### 7.1 Nhiều provider LLM (quyết định 3)

- **Registry** các adapter cùng một interface (`generate`, `generate_stream`, `vision`), mỗi adapter trả token lấy từ `usage` của API:
  - `anthropic` (Claude): giữ nguyên cách gọi của `codebase/ai.py`, thêm stream.
  - `gemini`: từ RAGslides `pptagent/llm_client` và Zentus.
  - `groq`: từ Zentus, có xoay vòng nhiều key.
  - `openrouter`, và `openai_compatible` (dùng chung cho OpenAI / vLLM / Ollama).
- **Định tuyến theo việc** trong `backend/config/llm.yaml`. Mỗi việc có một chuỗi dự phòng; provider đầu lỗi hoặc hết hạn mức thì chuyển sang provider sau:

  ```yaml
  tasks:
    generate:  [anthropic:claude-sonnet-5-5, gemini:gemini-2.5-flash]
    verify:    [anthropic:claude-haiku-5-5, groq:<model>]
    vision:    [gemini:<model>, groq:<model>]     # OCR + mô tả ảnh
    quiz:      [anthropic:claude-sonnet-5-5, groq:<model>]
  ```

- **Bảng giá** mỗi model để tính chi phí cho panel Agent verify và analytics. Trace ghi provider + model thật đã trả lời.
- Gói người dùng có thể quy định provider được dùng (vd gói trả phí dùng model mạnh hơn). Giai đoạn đầu chỉ để khung.

### 7.2 Người dùng, phân quyền và gói (quyết định 1: chỉ dựng khung, chưa áp dụng thật)

- **Vai trò** (quyền thao tác): `admin` · `giang_vien` · `bien_tap` (đội sản xuất) · `nguoi_dung`. Giữ phân quyền theo presentation của RAGslides (owner / editor / viewer).
- **Gói** (tính năng): `pho_thong` (miễn phí) và `tra_phi`. Mỗi gói khai báo trong `backend/config/plans.yaml`:

  | | pho_thong | tra_phi |
  |---|---|---|
  | Tài liệu / tháng, số trang tối đa | thấp | cao |
  | OCR + mô tả ảnh | ✗ | ✓ |
  | Voice (ký tự / tháng) | ít | nhiều |
  | Loại câu quiz | mc, tf | cả 7 loại + câu nhiều bước / tình huống |
  | Template | cơ bản | toàn bộ + template riêng |
  | Export | PDF, HTML | + PPTX, (sau: MP4) |
  | Model | rẻ | mạnh hơn |

  *(Các số "thấp / cao / ít / nhiều" để trống, điền khi có giá thật.)*
- **Cơ chế:** bảng `plans`, `user_plans`, `usage_counters` (theo tháng). Endpoint gắn dependency `require_feature("ocr")` hoặc `consume_quota("voice_chars", n)`.
- **Chưa áp dụng thật:** cờ `BILLING_ENFORCE=false`. Lúc này dependency **luôn cho qua**, chỉ ghi `usage_counters` và trả header / field `quota_warning` nếu vượt. Không có thanh toán; admin gán gói bằng tay. Bật cờ là chặn thật, không phải sửa code.

## 8. An toàn (giữ luật của repo)

- Không có endpoint xuất bản hay gửi cho học viên; trạng thái cuối luôn là `cho_duyet`.
- Nội dung tài liệu và kịch bản là dữ liệu, không phải lệnh. Tách chỉ dẫn chèn trước khi gắn nhãn; câu `TU_CHOI` không chấp nhận được.
- Chỉ dùng giọng có sẵn của nhà cung cấp; từ chối nhái giọng người thật.
- Kiểm mã đoạn bằng code: mọi `segment_id` hiện ra phải tồn tại.
- Khoá API chỉ để trong `.env`. Không commit file credentials. RAGslides đọc `app/core/helpers/credentials-dev.json`; phần này bỏ.

## 9. Kế hoạch theo giai đoạn

| GĐ | Nội dung | Ra được gì | Ước lượng |
|---|---|---|---|
| 0 | Khung `backend/`: config, DB SQLite (+ kiểm Postgres), storage, jobs, registry LLM + định tuyến, tracing, khung gói & quyền (cờ tắt); chép template / layout / font | `uvicorn` chạy, `/health`, đổi provider bằng config | 1 ngày |
| 1 | **Xử lý tài liệu** PDF / DOCX / PPTX → DocumentModel, bảng, ảnh, OCR, mã đoạn, index | Upload 1 PDF thật có bảng + ảnh → thấy đoạn, bảng, ảnh có mã | 1,5 ngày |
| 2 | `verification` (port từ `codebase/agent.py`) + scripts (dán + sinh từ tài liệu, đoạn A1..An) + cổng 1 | Màn 1–2 chạy trên tài liệu thật | 1 ngày |
| 3 | Slide: pptagent + template + loại slide mới + ảnh / bảng từ nguồn + bộ vẽ HTML trong `ui/` + API trang cho trình sửa + cổng 2 + export PPTX/PDF/HTML | Màn 3–4 (voice giả) | 2 ngày |
| 4 | Quiz: port Zentus + chiều sâu (§5) + kiểm từng phương án + PDF | Màn 5 | 1 ngày |
| 5a | Voice phần khung: job, hàng đợi giới hạn tốc độ, cắt đoạn theo giới hạn, cache, ước tính giá, timeline ước tính, với `FakeTTS` / `EdgeTTS` | Slide có giọng thuyết trình (giọng dev) | 1 ngày |
| 5b | Adapter API voice của bạn + danh sách giọng + điền giới hạn / giá thật | Giọng thật | 0,5 ngày (sau khi có API) |
| 6 | Tính năng còn lại của RAGslides: auth, chia sẻ, bình luận, cộng tác, template admin, analytics | Đủ "nguyên tính năng" | 1,5 ngày |
| 7 | Nối `ui/` sang API mới, bỏ lớp tương thích; test; chạy lại eval trên tài liệu thật | | 1 ngày |
| 8 | Trình sửa slide kiểu PPTist (frontend riêng) | Sửa slide tự do, lưu tự kiểm lại | ngoài ước lượng backend |

Tổng phần backend khoảng **10–11 ngày công**. GĐ 0–4 là bản dùng được; GĐ 6 nặng nhất mà ít liên quan tới bài toán kiểm duyệt.

**Về hackathon:** CP4 lúc 14:30 hôm nay, changelog đóng lúc 23:59. Backend này nên làm **sau** khi nộp, hoặc ở nhánh riêng. Nếu muốn một phần lên demo hôm nay, chỉ nên lấy **GĐ 1**: đọc được PDF có bảng và ảnh. Phần đó cũng phải ghi vào changelog §10, và không được đổi bộ câu thử hay chuẩn "đạt".

## 10. Rủi ro

- **Bản quyền:** cả RAGslides-be (`github.com/nguyenvanson1998`) lẫn BE_Zentus đều **không có file LICENSE**. Cần chủ repo đồng ý trước khi chép code vào repo nộp bài, và ghi nguồn trong `docs/ai-usage.md` hoặc README.
- **Định dạng slide:** JSON phần tử của RAGslides (shape / text / image có toạ độ) được thiết kế cho một trình sửa slide kiểu PPTist. `ui/` hiện tại không vẽ được định dạng này, nên phải thêm bộ vẽ (HTML/SVG) hoặc trình sửa.
- **OCR và mô tả ảnh tốn tiền và thời gian** với tài liệu 80 trang. Cần cache theo hash và cờ tắt.
- **Dependency nặng hơn nhiều:** PyMuPDF, pdfplumber, python-docx, python-pptx, SQLAlchemy, Alembic, Pillow. Để riêng trong `backend/requirements.txt`, không trộn với khung lab chỉ dùng thư viện chuẩn.

## 11. Quyết định

| # | Câu hỏi | Quyết định (28/11) | Ở đâu trong plan |
|---|---|---|---|
| 1 | Người dùng, phân quyền | Có vai trò + gói `pho_thong` / `tra_phi` có thêm tính năng; **chỉ dựng khung**, chưa áp dụng thật | §7.2 |
| 2 | DB | SQLite để test, nối được Postgres | §7 |
| 3 | LLM | Nhiều provider, định tuyến theo việc, có dự phòng | §7.1 |
| 4 | Frontend slide | Làm cả hai: bộ vẽ HTML để duyệt + trình sửa kiểu PPTist, cùng một JSON | §4 |
| 5 | Voice | API theo job; mốc thời gian chưa rõ → dựa vào kịch bản đã duyệt để chia đoạn và ước mốc; giọng cung cấp sau; giới hạn và giá xử lý bằng config | §4.1 |
| 6 | Bản quyền code RAGslides-be, BE_Zentus | **Còn mở**: cần chủ repo đồng ý | §10 |
| 7 | Thời điểm | **Còn mở**: đề xuất làm sau khi nộp hackathon hoặc trên nhánh riêng | §9 |

Khi có voice API, cần thêm: endpoint submit / poll (hoặc webhook), định dạng audio trả về, có mốc thời gian không, danh sách giọng, `max_chars_per_request`, `rpm`, số job đồng thời, đơn vị tính giá và đơn giá.
