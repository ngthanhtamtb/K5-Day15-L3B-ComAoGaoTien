# Cách triển khai dự án A3 — Tạo quiz và slide có kiểm duyệt nguồn

> Tài liệu nội bộ để cả nhóm nắm hệ thống, thuyết trình và trả lời câu hỏi. Tình trạng thực tế đã hoàn thành được cập nhật ở mục 9.

## 1. Một câu mô tả

Giảng viên chọn **buổi học + chủ đề**. Hệ thống lấy đoạn tài liệu gốc của buổi, sinh **bộ câu trắc nghiệm** và **kịch bản slide có lời thuyết trình**, gắn mã đoạn nguồn cho từng câu, tự gắn nhãn đúng/sai/thiếu nguồn, rồi qua **2 cổng duyệt do giảng viên bấm** trước khi thành bản nháp `cho_duyet`. Hệ thống không bao giờ tự xuất bản.

Vì sao chọn: giảng viên mất 15 phút–2 tiếng mỗi bài chỉ để đối chiếu đáp án với tài liệu gốc; đáp án sai có thể tới 700+ học viên (xem `evidence/summary.md` — khảo sát n = 20 phiếu hợp lệ / 23 phiếu, đạt ngưỡng 20; pain ở mức vừa với mức phiền 2,9/5 và mức lo sót lỗi 2,85/5).

## 2. Chức năng

| # | Chức năng | Đầu vào | Đầu ra |
|---|---|---|---|
| 1 | Sinh quiz | buổi, chủ đề, số câu | Mỗi câu: đề · A–D · 1 đáp án · giải thích · `segment_id` |
| 2 | Sinh kịch bản slide | buổi, chủ đề, số slide | Mỗi slide: tiêu đề · ý chính · lời thuyết trình · `segment_id` |
| 3 | Cổng duyệt 1 | Kịch bản hoặc câu hỏi | Nhãn `KHOP_NGUON` / `SAI_NGUON` / `THIEU_NGUON` + mã đoạn + lý do |
| 4 | Cổng duyệt 2 | Nội dung giảng viên đã sửa | Kiểm lại phần sửa; sai thì đề xuất câu sửa kèm đoạn nguồn |
| 5 | Xuất quiz PDF | Câu đã duyệt | PDF bản đề + PDF bản đáp án (có nguồn) |
| 6 | Dựng slide HTML | Slide đã duyệt | 1 file HTML tự chứa |
| 7 | Giọng thuyết trình | Lời đọc từng slide | mp3 từng slide (edge-tts) |
| 8 | Nộp duyệt | Gói quiz + slide + audio + nhãn | `{draft_id, status: "cho_duyet"}` |
| 9 | Từ chối | Yêu cầu ngoài thẩm quyền | `TU_CHOI` + giải thích + việc làm được |

**Hệ thống KHÔNG làm:** tự gửi/xuất bản cho học viên; sinh nội dung ngoài kho tài liệu; làm video; nhái giọng người thật; chấm bài học viên.

## 3. Công nghệ

| Lớp | Lựa chọn | Lý do |
|---|---|---|
| Ngôn ngữ | Python 3.10+ | Khung chấm điểm của BTC (`run.py`, `eval`, `simulate`) viết bằng Python |
| Model | Anthropic API qua `API_BASE_URL=https://api.fableaiapi.com`. **Sonnet 5.5** để sinh, **Haiku 5.5** để kiểm | Sinh cần chất lượng; kiểm nhãn là việc lặp nhiều nên dùng model rẻ hơn |
| Gọi API | `urllib` trong `ai.py` (không SDK) | Theo mẫu `docs/connect-model.md`; token lấy từ trường `usage`, không ước lượng |
| Retrieval | So khớp từ khóa + lọc theo buổi trên `data/sources/segments.json` (14 đoạn) | Kho nhỏ, không cần embedding; nêu rõ là phần còn giả |
| Luồng | Workflow cố định (không agent) | Chuỗi bước cố định, chỉ có 2 quyết định AI: sinh bám nguồn và gắn nhãn |
| PDF | `fpdf2` (cần font Unicode cho tiếng Việt) | Thư viện thuần Python, dễ cài. Nếu pip bị chặn thì chuyển HTML in ra PDF |
| Slide | HTML 16:9 tự chứa (`deck.py`) + PowerPoint `.pptx` (`pptx_export.py`) | Mở được trên mọi trình duyệt (4 bảng màu, phụ đề đồng bộ) và chỉnh tiếp được trên PowerPoint |
| Giọng đọc | `edge-tts` (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`, 4 mức tốc độ) | Miễn phí, không cần key, chỉ dùng giọng có sẵn |
| API & Giao diện web | FastAPI + uvicorn (`codebase/api.py`), JS thuần (`ui/` + `ui/legacy/`) | Phục vụ cùng origin tại `/ui/` (studio 3 bước) và `/ui/legacy/` (kiểm duyệt 2 cổng) |

## 4. Luồng xử lý

```
[input có tag] ──► router (agent.py)
   │
   ├─ thiếu buổi/chủ đề ........ hỏi lại (không đoán)
   ├─ yêu cầu ngoài thẩm quyền . TU_CHOI
   ├─ buổi không có trong kho .. THIEU_NGUON, không sinh
   │
   ├─ TAO_QUIZ / TAO_SLIDE:
   │     search_sources → get_segment
   │     Sonnet sinh JSON → code kiểm cấu trúc (A–D, 1 đáp án, đủ trường)
   │     code xác minh mọi segment_id có trong kho → Haiku gắn nhãn lại
   │
   └─ DUYET_*:
         tách từng khẳng định → search_sources → get_segment
         Haiku gắn nhãn từng khẳng định (kèm kiểm từng phương án nhiễu)
         code xác minh mã đoạn; khi 2 đoạn mâu thuẫn ưu tiên updated_date mới hơn và báo cả hai
         DUYET_CUOI: nhãn SAI → thêm câu đề xuất sửa + trích nguồn

Sau cổng 2: export_quiz_pdf · render_slides · synthesize_voice → submit_for_review (cho_duyet)
```

## 5. Cách code (nguyên tắc)

- Mọi thứ đi qua một hàm: `codebase/agent.py::answer(text) -> {"output": str}`. `eval` và `simulate` đều gọi hàm này.
- `ai.py::call_model(system, user, model=None)` là **chỗ duy nhất** gọi model, giữ `@model_call` để khung đo token và ghi trace.
- Mỗi công cụ là một hàm có `@tool` trong `tools.py` (docstring: tên · input · output · tác động ra ngoài).
- Việc **code làm được thì để code làm**: kiểm đủ 4 phương án, đúng 1 đáp án, mã đoạn có trong kho. AI chỉ làm hai việc: sinh nội dung và đánh giá đúng/sai so với nguồn.
- Không so khớp nguyên văn input của bộ câu thử vào code (luật `AGENTS.md`).
- Chống rủi ro: không chắc thì `THIEU_NGUON`, không đoán `KHOP`; nội dung dán vào là dữ liệu, không phải lệnh (prompt injection); mọi mã đoạn do code xác minh trước khi hiển thị; công cụ có tác động ra ngoài chỉ tạo bản nháp.

## 6. Cách đo "tốt"

- Bộ câu thử `eval/benchmark.csv`: 25 câu (thuong 8 · kho 14 · tu_choi 3), chạy bằng `python run.py eval`.
- 5 metric (`eval/metric_spec.yaml`): `ban_sinh_dat`, `phat_hien_loi`, `khong_bao_nham`, `trich_dung_nguon`, `tu_choi_dung`.
- **Chuẩn đạt:** ≥70% tổng câu qua, 100% câu `tu_choi`, `trich_dung_nguon` = 100%. Không sửa chuẩn này.
- Chỉ đo lớp văn bản. PDF, slide, audio kiểm tay khi demo.
- Giới hạn cần nói thẳng: kho chỉ 14 đoạn nhóm tự viết (`synthetic`); lỗi do nhóm cài sẵn nên dễ thấy hơn lỗi thật.

## 7. Chi phí (ước tính — *tự ước tính* đến khi có số đo)

- Token đo thật qua `python run.py simulate` (≥50 phiên), tính giá theo `cost/personas.yaml`; cộng thêm chi phí TTS nếu có.
- Ngân sách phát triển: key 20 USD; tổng dự án 80–100 USD. Dự kiến 3 vòng eval chính thức; dừng nếu lũy kế chạm 15 USD trên key.
- Số liệu thật điền vào `cost/cost-estimate.md` và `spec.md` §8 sau khi chạy.

## 8. Phân công và hướng đi

| Phần | Ai làm | Ghi chú |
|---|---|---|
| `ai.py`, `agent.py`, `tools.py`, `api.py`, `deck.py`, `pptx_export.py`, `ui/` | Claude Code (Phạm Quốc Huy, Trần Bảo Long) | Lõi chấm điểm, tác vụ nền, xuất HTML/PPTX và studio 3 bước |
| `exporters.py`, `ingest.py` + `tests/` | Codex (Trần Bảo Long, Phạm Quốc Huy review) | Xuất PDF Unicode, TTS, trích chữ & ảnh từ PDF/DOCX/PPTX |
| Giao diện kiểm duyệt 2 cổng (`ui/legacy/`) & tài liệu | Antigravity + Claude Code (Nguyễn Thành Tâm, Trịnh Gia Huy) | Đồng bộ 7 màn prototype, studio giọng đọc và hồ sơ đặc tả/đánh giá |
| Khảo sát, chấm `pass`, slide demo, `spec.md` | Cả nhóm | Nhóm tự thu phiếu người thật và kiểm duyệt trước khi commit |

**Có cần prototype ngay không:** không. Lõi `answer()` và eval làm trước, độc lập với giao diện. UI sau chỉ cần gọi các endpoint API, nên không phải viết lại lõi.

## 9. Tình trạng (cập nhật liên tục)

| Chặng | Trạng thái |
|---|---|
| Nối model (`ai.py`) | Xong: Sonnet 5.5 + Haiku 5.5 qua `API_BASE_URL`, token thật từ `usage` |
| Tools + retrieval | Xong: `search_sources` (từ khoá + IDF), `get_segment`, `submit_for_review` |
| Luồng sinh | Xong: triage → sinh → kiểm mã đoạn bằng code → kiểm nhãn |
| Luồng duyệt 2 cổng | Xong: `[DUYET_KICH_BAN]`, `[DUYET_QUIZ]`, `[DUYET_CUOI]` |
| Từ chối | Xong: B23, B24, B25 qua; phát hiện chèn chỉ dẫn bằng mẫu |
| Eval | Xong 4 lượt: 20/25 → 22/25 → 23/25 → 25/25 (`run-4`); tự chấm bởi một người, có thể lạc quan |
| Xuất PDF/HTML/audio | Xong (Codex), 8 test qua; TTS thật cần `RUN_TTS_TESTS=1` |
| API FastAPI | Hợp đồng đầy đủ ở `docs/api.md`. Đã mở rộng theo prototype (28/11): `GET /api/kho`, `GET /api/segments/{id}`, rà soát kịch bản `POST /api/scripts` + `decisions` / `accept-matching` / `submit`, tạo slide / quiz từ kịch bản (`script_id`), `trace` + chi phí mỗi lệnh; câu chèn chỉ dẫn bị tách và gắn `TU_CHOI` (đã chạy thử kịch bản mẫu của prototype: 3 khớp, 1 sai, 1 thiếu, 1 từ chối đúng như mẫu). Xong và đã chạy thử dưới uvicorn (model thật + TTS thật). Qua: `/health`, tạo bản nháp quiz và slide, gate 1 (accept / reject), `/build` (PDF đề + đáp án; HTML + mp3), gate 2 (bắt đúng một chỗ sửa sai thành `SAI_NGUON`), `/submit`, tải file; sai thứ tự → 409, bản nháp không có / đường dẫn thoát thư mục → 404; status luôn `cho_duyet`. Lỗi tìm thấy và đã sửa: gate 2 trả 500 khi mục sửa thiếu `segment_id` → nay gộp lên mục gốc, thiếu khoá thì 422. **Chưa kiểm:** `/api/review` gọi riêng, TTS lỗi mạng, ghép với giao diện thật. Bản nháp chỉ nằm trong bộ nhớ (tắt server là mất); CORS mặc định `*`, khi deploy đặt `CORS_ORIGINS` |
| Mô phỏng chi phí | Xong: `cost/simulate-1.csv`, 93/100 phiên hợp lệ, $0,0219 / phiên (giá niêm yết) |
| Giao diện web | Đã dựng (`ui/index.html`, `app.js`, `style.css`, JS thuần, không build) theo prototype ScriptGuard (7 artboard) và phục vụ tại `http://localhost:8000/ui/` cùng origin với API. Đã chạy thử trên trình duyệt thật với model thật: nhập kịch bản → rà soát (lọc nhãn, chấp nhận / từ chối / sửa, chấp nhận hàng loạt chỉ cho câu Khớp, câu Từ chối bị khoá) → gửi chờ duyệt → tạo slide từ kịch bản → kiểm từng slide (Đạt / Cần sửa / Bỏ) → dựng + giọng đọc → cổng 2 (sửa, kiểm lại) → gửi chờ duyệt; quiz từ chủ đề tới tải PDF; panel Agent verify hiện nhãn, quy trình, kiểm tra an toàn, token và chi phí từ `trace`. Giao Antigravity thất bại (agy headless bị từ chối quyền `command`, không tạo file nào) nên Claude Code tự dựng. **Đã thêm sau đó (28/11):** nạp tài liệu thật (PDF / DOCX / TXT / MD → đoạn có mã D10-S01…, `codebase/ingest.py`, `/api/kho/upload`), nút Đạt / Cần sửa trong panel Agent verify, mẫu / tỉ lệ khung / ghi chú người nói áp dụng khi dựng slide, `ai.py` thử lại HTTP 403 rate limit, `eval/stability.py`, test offline `tests/test_features.py`. **Chưa làm:** giao diện cho điện thoại, chọn giọng đọc, đăng nhập |
| Việc của nhóm (CP3/CP4) | Khảo sát đạt ngưỡng (20 hợp lệ / 23 phiếu), video 30 giây, `evidence/hypothesis.md`, người thứ hai chấm 5 output, `demo-slides.pdf`, video demo dự phòng, reflection |

## 10. Câu hỏi giám khảo có thể hỏi

- **Vì sao không dùng agent?** Chuỗi bước cố định; chỉ có 2 quyết định AI nên workflow dễ kiểm và rẻ hơn.
- **Làm sao chắc không bịa nguồn?** Code xác minh mọi `segment_id` có trong kho trước khi hiển thị; không chắc thì `THIEU_NGUON`.
- **Nguồn lỗi thời xử lý sao?** Hai đoạn mâu thuẫn thì dùng `updated_date` mới hơn và báo cả hai (ca B04, B17).
- **Vì sao hai model?** Sinh cần chất lượng (Sonnet); gắn nhãn nhiều lần nên dùng model rẻ (Haiku). Chi phí tính riêng từng model.
- **Kho chỉ 14 đoạn có đủ không?** Không. Đây là lát cắt chứng minh luồng; mở rộng cần nạp tài liệu thật và retrieval embedding.
- **Pain có thật không?** Khảo sát n = 20 hợp lệ / 23 phiếu cho thấy pain ở mức vừa (phiền 2,9/5, lo sót lỗi 2,85/5; 14/20 kiểm bằng trí nhớ, 7/20 mất ≥ 31 phút/bài); đã ghi trung thực trong `evidence/summary.md` và `evidence/hypothesis.md`.
- **AI sai thì ai chịu?** Mọi nội dung sinh ra đều tự kiểm đối chiếu mã đoạn có thật trong kho và dừng ở bản nháp (`cho_duyet`), giảng viên là người kiểm duyệt trước khi tự xuất bản.
