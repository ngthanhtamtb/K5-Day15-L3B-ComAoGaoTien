# EduGuard backend (RAGslides-be + quiz + voice)

Toàn bộ RAGslides-be được giữ nguyên (auth, presentations, templates, sinh outline/slide, media…).
Phần mở rộng nằm ở `app/edu/` và route `/api/v1/edu/*` (file `app/api/v1/endpoints/edu.py`).

## Chạy

> `.env` được ưu tiên hơn biến môi trường của máy (Windows có thể còn `GEMINI_API_KEY` cũ ở mức hệ thống).

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # điền FERNET_KEY + key của ít nhất một provider LLM (ANTHROPIC / GEMINI / GROQ…)
python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"   # -> FERNET_KEY
uvicorn main:app --host 0.0.0.0 --port 8077 --reload
# Swagger: http://localhost:8077/api-docs  (nhóm "EduGuard" và "EduGuard · review flow")
python -m pytest -q tests/    # 27 test, không gọi API thật (LLM giả, TTS im lặng, SQLite tạm)
```

Mặc định dùng **SQLite** (`data/eduguard.db`), không cần cài Postgres; đổi `DATABASE_URL` là chạy Postgres.
Các route `/edu/*` lưu file JSON trong `EDU_DATA_DIR` (mặc định `data/edu/`, đã gitignore); ảnh/audio
được phục vụ qua `/static/edu/...` ở bất kỳ đâu `EDU_DATA_DIR` nằm.

## Cấu trúc `app/edu/`

| Thư mục | Vai trò |
|---|---|
| `docparse/docx_parser.py` | Parser .docx gốc: giữ thứ tự ảnh/bảng, auto-numbering ("Câu %1.", "A."), ô gộp, bảng lồng, text box, OMML→LaTeX, WMF/EMF→PNG, định dạng run (gạch chân/đỏ/highlight) |
| `docparse/local_parsers.py` | **Mặc định cho PDF/PPTX, chạy tại máy**: PDF (PyMuPDF) giữ bbox từng khối, heading theo cỡ chữ, bảng `find_tables` (dự phòng pdfplumber), ảnh kèm vị trí + chú thích "Hình…", bỏ header/footer lặp, trang scan → OCR (nếu bật) hoặc giữ ảnh trang; PPTX lấy tiêu đề, cấp gạch đầu dòng, bảng, ảnh (cả trong group), ghi chú người nói |
| `docparse/other_parsers.py` | Docling (`EDU_PDF_ENGINE=docling`), server ngoài `EXTRACT_DOC_API_URL` chỉ khi bật rõ `EDU_PDF_ENGINE=remote`; .doc/.ppt qua LibreOffice |
| `docparse/service.py` | Ingest → markdown + chunk theo heading (ảnh/bảng không bị tách khỏi đoạn văn) |
| `retrieval/bm25.py` | BM25 không phụ thuộc thư viện (unigram + bigram tiếng Việt) cho source grounding |
| `quiz/extractor.py` | Trích câu hỏi từ đề: MCQ, Đúng/Sai a)–d), trả lời ngắn; đáp án từ bảng đáp án / "Đáp án: B" / gạch chân / chữ đỏ / highlight / in đậm duy nhất |
| `quiz/engines.py` | `LLMQuizEngine` (router nhiều provider, task `quiz`, có gửi ảnh; tên cũ `GeminiQuizEngine` vẫn dùng được) và `ZentusQuizEngine` (hàm BE_Zentus bên ngoài, lỗi thì tự về router). Prompt có phần **chiều sâu**: câu tình huống, nhiều bước (≥2 đoạn), đọc bảng/hình, mỗi phương án nhiễu ghi `misconception` |
| `quiz/evaluator.py` | Eval → `baseMetrics`, `source`, `fixes` (khớp tên trường của frontend) |
| `tts/` | Provider TTS: `silent` (test), `http` (cấu hình bằng .env) |
| `voice/service.py` | Lời giảng `slide.remark`, TTS có cache, gắn audio element PPTist (autoplay) |

## Phần thêm theo plan `backend/ARCHITECTURE.md` (28/11)

| Thư mục / file | Vai trò |
|---|---|
| `app/core/db_types.py` | `JSONB` / `UUID` chạy được cả SQLite lẫn Postgres (model không còn import dialect Postgres) |
| `app/core/llm/` + `config/llm.yaml` | **Nhiều provider**: anthropic, gemini, openai, groq (xoay vòng nhiều key), openrouter, ollama, fake. Định tuyến theo việc (`generate`, `script`, `quiz`, `verify`, `vision`, `cheap`), lỗi 429/5xx/timeout thì chuyển provider sau. Token lấy từ `usage`; giá theo bảng trong yaml, model chưa có giá thì chi phí là `null` (không đoán) |
| `app/core/llm/trace.py` | Trace cho panel Agent verify: các bước, số lần gọi model, token, chi phí, lỗi — trả kèm mọi response có gọi model |
| `app/core/jobs.py` | Job nền trong tiến trình (không cần Kafka) + lưu trạng thái + SSE tiến độ |
| `app/edu/verify/` | Gắn nhãn **KHOP_NGUON / SAI_NGUON / THIEU_NGUON / TU_CHOI** (port từ prototype đã chạy 6 lượt eval). Model gắn nhãn theo chỉ số nên không bịa được khẳng định; câu có chỉ dẫn chèn → `TU_CHOI` bằng code; không có đoạn nguồn → `THIEU_NGUON` không gọi model; mã đoạn model đưa ra được code kiểm lại. Câu trắc nghiệm: kiểm từng phương án (bắt câu 2 đáp án đúng) |
| `app/edu/scripts/` | Kịch bản (màn 1–2 prototype): dán bản nháp (`Slide N:` hoặc đoạn trống) hoặc sinh từ tài liệu; mỗi slide chia đoạn **A1..An** gắn nguồn; giáo viên sửa (kiểm lại ngay) / giữ nguyên / bỏ câu bất cứ lúc nào. **Không có bước chờ duyệt**: mọi câu được dùng cho slide và giọng đọc trừ câu bị bỏ hoặc câu chứa chỉ dẫn chèn (`included()`); `needs_review()` đếm câu "cần xem" |
| `app/edu/slides_builder.py` | Kịch bản đã duyệt → slide PPTist bằng engine template của RAGslides; ô ảnh của template lấy **hình trong tài liệu gốc** (không sinh ảnh AI); mỗi slide có `remark` (lời đọc), khối `eduguard` (nhãn từng đoạn, mã nguồn, mốc audio) và phần tử audio tự phát |
| `app/edu/voice/limits.py`, `script_voice.py`, `tts/job_provider.py` | Voice **theo job**: API submit → poll → lấy audio (`TTS_MODE=job`); giới hạn `TTS_RPM` + `TTS_CONCURRENCY`, thử lại 429/5xx theo `Retry-After`, cắt đoạn dài theo `TTS_MAX_CHARS` ở ranh giới câu; **ước tính trước** ký tự / số request / thời lượng / chi phí; mỗi đoạn một clip (cache theo nội dung, sửa 1 đoạn chỉ tính tiền đoạn đó), mỗi slide một track có mốc A1..An lấy từ thời lượng thật; mốc từng câu lấy từ API nếu có, không thì ước theo âm tiết (`timing_source: uoc_tinh`) |
| `app/edu/billing/` + `config/plans.yaml` | **Khung** vai trò (`admin`, `giang_vien`, `bien_tap`, `nguoi_dung`) và gói `pho_thong` / `tra_phi` (map từ cột `subscription_type` sẵn có). `BILLING_ENFORCE=false`: không chặn gì, chỉ ghi lượng dùng theo tháng và trả `quotaWarnings`; bật `true` thì trả 402, không cần sửa code. Admin gán gói bằng tay |

### API mới (`/api/v1/edu`, nhóm "EduGuard · review flow")

| Method | Path | Việc |
|---|---|---|
| POST | `/documents/async` | Upload + parse thành job (PDF lớn, OCR) → `jobId` |
| GET | `/documents/{docId}/pages/{n}` | Khối + ảnh của một trang kèm bbox (tô sáng đoạn nguồn) |
| POST | `/verify` | Gắn nhãn danh sách câu với một tài liệu |
| POST | `/scripts` | Tạo kịch bản: `noiDung` (dán) hoặc `chuDe` (sinh từ tài liệu) |
| GET | `/scripts/{id}` | Kịch bản + đếm nhãn / quyết định |
| POST | `/scripts/{id}/decisions` (accept · reject · edit · reset, nhiều câu một lần) · `/revise` · `/accept-matching` | Sửa / giữ / bỏ câu |
| POST | `/documents/{docId}/deck` | **Một bước** (`khung`: `bai_giang` \| `gon`): AI thiết kế slide theo khung (xem "Khung slide") → kiểm từng câu với nguồn → gắn hình / bảng của tài liệu (theo đoạn câu trích) → giọng đọc → slide HTML (job). Voice lỗi thì vẫn ra slide, kèm `voiceError` |
| POST | `/scripts/{id}/html` | Dựng lại slide HTML sau khi sửa câu (không gọi model). Job voice cũng tự dựng lại |
| GET | `/templates` | Template slide |
| POST | `/scripts/{id}/slides` | Slide PPTist từ kịch bản đã duyệt |
| POST | `/scripts/{id}/voice/estimate` | Ước tính ký tự, request, thời lượng, chi phí, hạn mức |
| POST | `/scripts/{id}/voice` | Sinh giọng (job) |
| POST | `/quizzes/{id}/questions/{qid}/decision` · `/verify` | Giữ / bỏ / kiểm lại một câu (PDF gồm mọi câu chưa bỏ) |
| GET | `/jobs/{id}` · `/jobs/{id}/events` (SSE) · POST `/jobs/{id}/cancel` | Theo dõi job |
| GET | `/plans` · `/me/plan` · `/llm/status` | Gói, lượng dùng, provider nào có key |
| PUT | `/api/v1/admin/users/{id}/plan` | Admin gán gói / vai trò |

Không có bước chờ duyệt và không có endpoint xuất bản (đã bỏ `/scripts/{id}/submit`, `/quizzes/{id}/submit`). Trường `status` cũ trong dữ liệu được giữ để tương thích nhưng không còn chặn thao tác nào.

### Sửa lỗi / an toàn trong lúc làm

- Middleware cũ in **toàn bộ header** (cả `Authorization: Bearer …`) ra log → giờ chỉ log method, path, status.
- `storage.url_for` tính URL theo thư mục `data/` nên hỏng khi `EDU_DATA_DIR` nằm chỗ khác → mount riêng `/static/edu`.
- `pptx_utils` đọc `FERNET_KEY` bằng `os.getenv` nên không thấy key chỉ nằm trong `.env` → đọc thêm từ `settings`.
- Mặc định không còn gửi PDF/PPTX tới `124.158.5.35`.
- `vertexai` chỉ import khi sinh ảnh bìa (không cần cài để chạy phần còn lại).

### Chưa làm / còn giả

- Chưa nối API voice thật (chờ API); chưa thử provider LLM thật nào trong môi trường này — mọi test dùng LLM giả.
- Export PPTX/PDF của presentation (`export.py`) vẫn là khung rỗng của RAGslides.
- Bảng trong slide mới dừng ở việc giữ `tableIds` trong khối `eduguard`, chưa vẽ thành phần tử bảng PPTist.
- Chưa có Alembic migration; DB Postgres có sẵn cần thêm cột `users.role` bằng tay (câu lệnh trong `.env.example`).
- Lượng dùng `llm_tokens` chưa được ghi (chỉ có `documents`, `quiz_questions`, `voice_chars`).

## Khung slide (`app/edu/slide_frame.py`)

Phân tích các khung slide giảng dạy hay dùng và cách áp dụng vào hệ thống:

| Khung tham khảo | Ý chính | Áp dụng |
|---|---|---|
| Mạch bài học (Gagné, rút gọn) | mở bài → nội dung → củng cố → kiểm tra | `khung=bai_giang`: bìa → **Nội dung chính** → slide nội dung → **Tóm tắt** → **Câu hỏi nhanh** → kết. `khung=gon`: chỉ slide nội dung |
| Assertion–Evidence (Alley) | tiêu đề là một câu khẳng định, thân slide là bằng chứng trực quan | prompt bắt tiêu đề là câu khẳng định ≤ 12 từ; thân slide ưu tiên hình / bảng **của tài liệu**, sơ đồ so sánh, quy trình |
| Nguyên tắc đa phương tiện (Mayer) | một ý mỗi slide, bớt chữ, lời đọc không đọc lại chữ trên slide, chú thích cạnh hình, hình + giọng | ≤ 4 dòng × ≤ 14 từ; lời đọc "giải thích thêm"; chú thích ngay dưới hình; giọng đọc theo đoạn A1..An, phụ đề + tô sáng dòng đang nói |
| Retrieval practice | tự nhớ lại giúp nhớ lâu hơn đọc lại | slide **Câu hỏi nhanh**: câu hỏi + nút "Xem đáp án" (tự mở khi giọng đọc tới đáp án) |

**Khung từng slide** (model chọn, hệ thống kiểm lại không cần model):

| Khung | Điều kiện, nếu thiếu thì chuyển về `bullets` |
|---|---|
| `bullets` Ý chính | 2–4 dòng ngắn |
| `image_text` Hình + ý | id hình có thật trong tài liệu và là hình thật (`is_figure`: bỏ trang scan, logo / icon < ~100×100 pt) |
| `table` Bảng | id bảng có thật; kèm một câu rút ra |
| `comparison` So sánh | đúng 2 cột, mỗi cột ≥ 1 ý |
| `process` Quy trình | 3–6 bước; tên kiểu "Bước 2" được thay bằng mô tả |
| `key_fact` Khái niệm / con số | giá trị phải **có nguyên văn** trong đoạn nguồn câu đó trích (con số không bao giờ bịa) |
| `agenda`, `summary`, `check` | dựng bởi `outline()` |

Kiểm nguồn: mọi câu có nội dung (cả tóm tắt và đáp án câu hỏi nhanh) đều được kiểm như trước. Câu dẫn dắt
(`vai_tro=dan_dat`, nhãn `DAN_DAT`) chỉ gồm tên các slide / câu hỏi, không chứa thông tin mới, nên không gửi đi kiểm
(vẫn chặn chỉ dẫn chèn → `TU_CHOI`). Đoạn nguồn mà model trích (`segment_id`) được đưa vào bằng chứng cho bộ kiểm
(`check_items(hints=...)`): nhờ đó tài liệu tiếng Anh + lời đọc tiếng Việt vẫn kiểm được (trước đây BM25 không khớp từ
nào nên ra `THIEU_NGUON` hàng loạt). Nhãn vẫn do bộ kiểm quyết theo nội dung.

Slide HTML (`html_deck.py`): khung cố định 1280×720 co theo cửa sổ (xem trước = trình chiếu), lề 72px, nhãn phần +
tiêu đề, vùng bằng chứng, chân slide "Nguồn: tr. …" + số trang, thanh tiến độ. PPTist (`slides_builder.py`) dùng
cùng dữ liệu (`extra.cot / buoc / nhan_manh / cau_hoi`).

**Chạy thật (Gemini 2.5 Flash, 28/11):** bài báo tiếng Anh 14 trang, 6 slide nội dung → 9 slide, 4 lần gọi model,
~65 giây: 23/23 câu khớp nguồn, 2 câu dẫn dắt; khung dùng: hình (img004), quy trình 4 bước, so sánh, tóm tắt,
câu hỏi nhanh. Logo tạp chí ở trang 1 không còn bị đưa lên slide.

## Nối BE_Zentus

```
QUIZ_ENGINE=zentus
ZENTUS_PATH=E:/Python_Project/VinAI_Lab/BE_Zentus
ZENTUS_GENERATE_FN=<module>:<function>
```
Hàm được gọi với các tham số mà nó khai báo trong số: `text|content|document` (markdown),
`chunks`, `num_questions|n`, `language`, `bloom_mix`, `question_types`, `images`.
Sync/async đều được; trả list dict / {"questions": [...]} / pydantic / chuỗi JSON đều được.
Tên trường thường gặp (`question|stem`, `choices|options`, `answer|correct_answer`, `explanation`…)
được map tự động trong `normalise_question()`. Nếu import lỗi, hệ thống tự dùng router LLM và ghi log.

## Nối API voice

Đổi `TTS_PROVIDER=http` và điền `TTS_API_URL`, `TTS_API_KEY`, `TTS_REQUEST_TEMPLATE`,
`TTS_RESPONSE_TYPE` (`binary` | `json_base64` | `json_url`), `TTS_RESPONSE_FIELD`.
API kiểu job (submit → poll): thêm `TTS_MODE=job`, `TTS_SUBMIT_URL`, `TTS_POLL_URL` (có `{job_id}`),
`TTS_JOB_ID_FIELD`, `TTS_STATUS_FIELD`, `TTS_DONE_VALUES`, `TTS_FAILED_VALUES` — không cần viết code.
Có số liệu của API thì điền `TTS_MAX_CHARS`, `TTS_RPM`, `TTS_CONCURRENCY`, `TTS_PRICE_UNIT`,
`TTS_PRICE_PER_UNIT`; nếu API trả thời lượng / mốc thời gian: `TTS_DURATION_FIELD`, `TTS_TIMINGS_FIELD`.
Danh sách giọng: override `list_voices()` của provider khi có.

## API chính (`/api/v1/edu`)

| Method | Path | Việc |
|---|---|---|
| POST | `/documents` | Upload + parse (docx/pdf/pptx/doc/md) |
| GET | `/documents/{docId}` | Blocks, images, tables, chunks |
| GET | `/documents/{docId}/search?q=` | Tìm đoạn nguồn |
| POST | `/documents/{docId}/quiz/extract` | Trích câu hỏi từ đề có sẵn |
| POST | `/documents/{docId}/quiz/generate` | Sinh câu hỏi (BE_Zentus / Gemini) |
| GET | `/quizzes/{quizId}` | Lấy bộ quiz |
| POST | `/quizzes/{quizId}/evaluate` | Eval (`{"useLlm": false}` = chỉ kiểm tra tất định) |
| PATCH | `/quizzes/{quizId}/questions/{qid}` | Giáo viên sửa câu |
| POST | `/quizzes/{quizId}/questions/{qid}/fixes/{fixId}/apply` · `/undo` | Áp dụng / hoàn tác sửa |
| POST | `/slides/scripts` | AI viết lời giảng cho slide trống (PPTist JSON) |
| POST | `/slides/voice` | TTS từng slide, gắn audio element, trả manifest thời lượng |
| POST | `/presentations/{id}/voice` | Voice một presentation đã lưu trong DB (cần đăng nhập) |
| POST | `/voice/synthesize` · GET `/voice/voices` | TTS đơn lẻ / danh sách giọng |

## Trình xem & sửa slide: PPTist

RAGslides đã sinh đúng JSON của PPTist, nên dùng PPTist làm editor:

1. `git clone https://github.com/pipipi-pikachu/PPTist && cd PPTist && npm install`
2. Copy `frontend-integration/pptist/eduguardBridge.ts` vào `PPTist/src/` và gọi
   `installEduguardBridge('http://localhost:3000')` trong `src/main.ts` sau `app.mount('#app')`
   (origin = địa chỉ app React của bạn).
3. `npm run dev` (mặc định http://localhost:5173)
4. Trong React: dùng `frontend-integration/react/PptistEditor.tsx` và `eduApi.ts`.

PPTist dùng giấy phép **AGPL-3.0**: nếu cung cấp sản phẩm cho người khác qua mạng thì phải
công khai mã nguồn phần sửa đổi, hoặc liên hệ tác giả mua giấy phép thương mại.

## Đã kiểm thử

Đề mẫu tiếng Việt có ảnh, bảng gộp ô, công thức OMML, đáp án dạng auto-numbering, câu
Đúng/Sai và trả lời ngắn: trích 5/5 câu, đáp án đúng 5/5 bằng bảng đáp án; bỏ bảng đáp án
vẫn nhận ra đáp án bằng gạch chân và chữ đỏ. Luồng voice: tạo audio, gắn element, cache khi chạy lại.
Chưa kiểm thử: gọi Gemini thật, BE_Zentus thật, API TTS thật, PDF qua Docling.
