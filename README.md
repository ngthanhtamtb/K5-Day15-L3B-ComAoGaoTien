# ComAoGaoTien — ScriptGuard: Tạo slide thuyết trình có giọng đọc & quiz trắc nghiệm bám nguồn (Track A · A3)

**Thành viên, lớp, track:** xem [TEAMS.md](TEAMS.md) (`L3B` · `Track A` · 4 thành viên).

*Lát cắt:* Giảng viên phụ trách bài pre-class chọn **một buổi học + một chủ đề** (hoặc tải tài liệu PDF / DOCX / PPTX / TXT / MD của buổi lên) → hệ thống trích chữ và ảnh minh hoạ, cắt thành các đoạn nguồn có mã `segment_id` → AI sinh **(a) bộ slide bài giảng kèm lời thuyết trình tự nhiên** và **(b) bộ câu hỏi trắc nghiệm 4 phương án A–D**, tự kiểm đối chiếu từng ý / từng đáp án với đoạn nguồn (`KHOP_NGUON` / `SAI_NGUON` / `THIEU_NGUON`) → xuất **slide HTML 16:9 + PowerPoint (`.pptx`) + giọng đọc tiếng Việt (`edge-tts`)** và **2 file PDF quiz** (bản đề + bản đáp án kèm mã nguồn), đồng thời hỗ trợ luồng **2 cổng duyệt của giảng viên** trước khi chốt bản nháp `cho_duyet` (hệ thống **không** tự xuất bản).

---

## Chạy trong 3 phút

### 1. Chạy dòng lệnh (CLI) & bộ đánh giá — chỉ cần Python 3.10+ (thư viện chuẩn)

Bộ khung chấm điểm (`run.py`, `codebase/agent.py`, `codebase/ai.py`, `eval/run_eval.py`, `cost/simulate.py`) **chỉ dùng thư viện chuẩn của Python 3.10+**, không cần `pip install`.

```bash
# 1. Tạo file .env và điền MODEL_PROVIDER=anthropic, API_KEY=..., API_BASE_URL=...
cp .env.example .env

# 2. Kiểm tra bộ câu thử, metric_spec và TEAMS.md
python run.py check

# 3. Chạy bản chạy thử ở dòng lệnh (chưa điền .env sẽ chạy chế độ giả "fake")
python run.py

# 4. Thử nối model thật với 3 câu đầu
python run.py eval --try
```

*(Trên macOS/Linux có thể thay `python` bằng `python3`; trên Windows dùng `python` hoặc `py`.)*

### 2. Chạy Giao diện Web & xuất Slide HTML / PPTX / Giọng đọc / Quiz PDF

Giao diện web và lớp xuất file dùng thêm `fastapi`, `uvicorn`, `edge-tts`, `fpdf2`, `pypdf`, `pillow`, `python-pptx`:

```bash
python -m pip install -r requirements.txt
python -m uvicorn api:app --app-dir codebase --port 8000
```

Mở trình duyệt tại:
- **`http://localhost:8000/ui/`** — **Giao diện chính (3 bước nhanh):** Tải tài liệu (PDF / DOCX / PPTX / TXT / MD, tự trích chữ & ảnh) → Tạo slide 16:9 (4 bảng màu, chèn ảnh từ tài liệu, thu giọng thuyết trình Hoài My / Nam Minh, tải `.pptx` / `.html` / `.zip`) → Tạo quiz trắc nghiệm & tải 2 file PDF đề thi + đáp án có mã nguồn.
- **`http://localhost:8000/ui/legacy/`** — **Giao diện kiểm duyệt 2 cổng ScriptGuard:** Rà soát kịch bản câu-theo-câu, duyệt từng slide / từng câu quiz qua Cổng 1 → Cổng 2 và xem chi tiết trace / chi phí trong panel `Agent verify`.
- API docs tự động tại `http://localhost:8000/docs`, hợp đồng chi tiết ở [docs/api.md](docs/api.md).

---

## Lệnh

| Lệnh | Làm gì |
|---|---|
| `python run.py` | Chạy bản chạy thử CLI (gõ đầu vào có tag `[TAO_QUIZ]`, `[TAO_SLIDE]`, `[DUYET_KICH_BAN]`, `[DUYET_QUIZ]`, `[DUYET_CUOI]`, nhận kết quả kèm số lần gọi model / token) |
| `python run.py check` | Kiểm `eval/benchmark.csv` (25 câu: `thuong` 8 · `kho` 14 · `tu_choi` 3 · `nguoi_dung` 10/25), `eval/metric_spec.yaml` (5 metric) và `TEAMS.md` (4 thành viên) |
| `python run.py eval --try` | Chạy thử 3 câu đầu → `eval/run-try.csv` (không tính là lượt chính thức) |
| `python run.py eval` | Chạy trọn bộ 25 câu qua `codebase/agent.py` → `eval/run-N.csv` + `traces/run-N.jsonl` |
| `python run.py score eval/run-4.csv` | In % đạt tổng và theo từng `type` (`run-1`: 20/25 = 80% → `run-4` & `run-6`: 25/25 = 100%) |
| `python eval/stability.py --runs 3` | Đo độ ổn định 25 câu × 3 lần chạy độc lập → `eval/stability-1.csv` / [eval/stability-1.md](eval/stability-1.md) (nhãn ổn định 24/25 câu) |
| `python run.py simulate --try` | Thử mô phỏng chi phí 10 phiên → `cost/simulate-try.csv` |
| `python run.py simulate --rate-from eval/run-4.csv` | Mô phỏng chi phí theo `cost/personas.yaml` → `cost/simulate-1.csv` (93/100 phiên hợp lệ, \$0,0219 / task thành công) |
| `python -m unittest discover -s tests` | Chạy 36 unit test offline cho `ingest.py`, `exporters.py`, `deck.py`, `pptx_export.py` và `api.py` |

---

## Cấu trúc bản chạy thử

| File | Vai trò |
|---|---|
| `codebase/agent.py` | `answer(text)` & `create_from_doc(...)` — workflow cố định (`spec.md` §4): phân loại yêu cầu (Haiku) → tra nguồn → sinh quiz/slide (Sonnet, chia lô tự động cho tài liệu dài) → code xác minh cấu trúc & `segment_id` → kiểm nhãn (Haiku) |
| `codebase/ai.py` | `call_model(system, user, model=None)` — chỗ duy nhất gọi model AI, lấy token thật từ trường `usage`, tự thử lại khi gặp `429`/`5xx`/`403 rate_limit` hoặc chạm `max_tokens` |
| `codebase/tools.py` | Công cụ `@tool`: `search_sources` (từ khoá + IDF bỏ dấu + ưu tiên tiêu đề), `get_segment`, `submit_for_review` (luôn trả `status="cho_duyet"`) |
| `codebase/ingest.py` | Nạp tài liệu thật (PDF / DOCX / PPTX / TXT / MD): trích chữ + trích ảnh minh hoạ gắn theo đoạn `D10-S01…` (lưu cục bộ ở `data/uploads/`, tự tách biệt khi chạy `eval`) |
| `codebase/deck.py` & `pptx_export.py` | Dựng bộ slide HTML 16:9 tự chứa (4 bảng màu, chèn ảnh trích từ tài liệu, phụ đề đồng bộ giọng đọc) và xuất file PowerPoint `.pptx` |
| `codebase/exporters.py` | Xuất quiz ra 2 file PDF Unicode (đề thi + đáp án kèm nguồn), điều phối dựng slide và tổng hợp giọng đọc tiếng Việt bằng `edge-tts` |
| `codebase/api.py`, `ui/`, `ui/legacy/` | FastAPI server (tác vụ nền có bước tiến trình thật, nghe thử/thu lại giọng đọc, tải gói `.zip`), giao diện chính 3 bước (`ui/`) và giao diện kiểm duyệt 2 cổng (`ui/legacy/`) |

---

## Phần nào thật, phần nào giả

| Thành phần | Thật / Giả | Ghi chú |
|---|---|---|
| Lời gọi AI ở quyết định trung tâm (`ai.py`) | **Thật** | Model: `claude-sonnet-5-5` (sinh quiz / slide) + `claude-haiku-5-5` (phân loại yêu cầu & gắn nhãn kiểm nguồn); token đọc trực tiếp từ `usage` của API |
| Kiểm cấu trúc & xác minh mã đoạn (`agent.py`, `tools.py`) | **Thật** | Code kiểm đủ 4 phương án A–D, đúng 1 đáp án, `segment_id` tồn tại thật trong kho và lọc bỏ khẳng định lạc đề |
| Xuất Slide HTML, PowerPoint, PDF Quiz & Giọng đọc (`deck.py`, `pptx_export.py`, `exporters.py`) | **Thật** | Xuất `.html` 16:9, `.pptx` (`python-pptx`), gói `.zip`, 2 file `.pdf` tiếng Việt (`fpdf2`) và `.mp3` giọng `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural` (`edge-tts`) |
| Nạp tài liệu & trích ảnh thật (`ingest.py`) | **Thật** | Đọc PDF / DOCX / PPTX / TXT / MD, trích cả văn bản lẫn hình ảnh minh hoạ trong tài liệu và gắn về đúng đoạn nguồn |
| Kho tài liệu gốc dùng chấm `eval` (`data/sources/segments.json`) | **Giả lập (`synthetic`)** | 14 đoạn do nhóm viết tóm tắt từ 3 buổi học (1, 4, 7), có cài 1 đoạn bản cũ (`D01-S06`, 32K vs 128K) để đo phát hiện nguồn lỗi thời |
| Truy xuất đoạn nguồn (`search_sources`) | **Đơn giản hoá** | So khớp từ khoá + trọng số IDF bỏ dấu tiếng Việt (chưa dùng vector embedding; PDF dạng ảnh quét chưa có OCR) |
| Xuất bản lên LMS (`submit_for_review`) | **Giả lập lưu nháp** | Chỉ lưu bản nháp cục bộ ở `drafts/` (trạng thái `cho_duyet`), **không** nối LMS pre-class thật và không tự động xuất bản cho học viên |

---

## Dùng AI vào việc gì

Nhóm dùng **Claude Code** để viết lõi workflow (`codebase/ai.py`, `tools.py`, `agent.py`, `api.py`, `deck.py`, `pptx_export.py`), giao diện `ui/` và tổng hợp bảng số liệu từ log chạy thật; dùng **Codex** để viết mô-đun xuất PDF/TTS (`exporters.py`), nạp tài liệu (`ingest.py`) cùng bộ unit test; dùng **Antigravity** để rà soát đặc tả, hoàn thiện giao diện kiểm duyệt (`ui/legacy/`) và đồng bộ tài liệu dự án. Toàn bộ câu hỏi khảo sát gửi người thật (n = 20 hợp lệ / 23 phiếu), quyết định thiết kế, chuẩn "đạt" (`spec.md` §7) và kiểm duyệt thay đổi trước khi commit đều do các thành viên nhóm thực hiện. Chi tiết xem tại [docs/ai-usage.md](docs/ai-usage.md).

---

## Bảy hạng mục bắt buộc — nằm ở file nào

| # | Hạng mục | File |
|---|---|---|
| 1 | Bằng chứng pain | `evidence/` (tổng hợp ở [evidence/summary.md](evidence/summary.md) · kiểm giả thuyết ở [evidence/hypothesis.md](evidence/hypothesis.md) · log khảo sát n = 20 hợp lệ ở [evidence/survey/results.csv](evidence/survey/results.csv)) |
| 2 | Impact có số | [spec.md](spec.md) §2 |
| 3 | Thiết kế giải pháp | [spec.md](spec.md) §4 · [docs/implementation.md](docs/implementation.md) · [docs/api.md](docs/api.md) |
| 4 | Bản chạy thử làm trọn lát cắt | `codebase/` · `ui/` · `ui/legacy/` · lệnh chạy ở mục [Chạy trong 3 phút](#chạy-trong-3-phút) |
| 5 | Định nghĩa "tốt" + bộ câu thử + báo cáo đánh giá | [data/DATA_CARD.md](data/DATA_CARD.md) · [eval/benchmark.csv](eval/benchmark.csv) · [eval/metric_spec.yaml](eval/metric_spec.yaml) · [eval/README.md](eval/README.md) · [eval/report.md](eval/report.md) · [eval/stability-1.md](eval/stability-1.md) |
| 6 | Mô phỏng chi phí khi dùng thật | [cost/personas.yaml](cost/personas.yaml) · [cost/simulate-1.csv](cost/simulate-1.csv) · [cost/cost-estimate.md](cost/cost-estimate.md) |
| 7 | Slide + demo + video dự phòng | [demo-slides.pdf](demo-slides.pdf) ở thư mục gốc (nguồn: [slides/demo-slides.html](slides/demo-slides.html)) |
| + | *Bonus:* người dùng thử | [validation/log.md](validation/log.md) |
