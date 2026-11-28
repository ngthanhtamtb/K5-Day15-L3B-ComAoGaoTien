# Khai báo dùng AI

README của nhóm có mục "Dùng AI vào việc gì" (2–3 dòng, bắt buộc). Ghi chi tiết vào bảng dưới đây.

> Luật của đề: dùng AI để làm bài thoải mái, nhưng **ai không giải thích được phần có tên mình thì phần đó nhận 0 điểm**. Khai thiếu không bị trừ; giấu mới bị.

## 1. Công cụ AI nhóm dùng khi làm bài

| Công cụ | Vai trò |
|---|---|
| **Claude Code** (Claude Sonnet 5.5) | Tech lead: viết lõi workflow, giao diện, tổng hợp số liệu từ log chạy thật, điều phối hai công cụ còn lại |
| **Codex** | Viết mô-đun độc lập: xuất PDF / giọng đọc, nạp tài liệu, unit test |
| **Antigravity** | Rà soát đặc tả, giao diện kiểm duyệt cũ, đồng bộ tài liệu |

Mọi thay đổi do công cụ AI viết đều được thành viên xem `git diff` trước khi commit.

## 2. Bảng khai báo

| Việc | Công cụ AI | AI làm gì | Người kiểm/sửa gì | Ai phụ trách |
|---|---|---|---|---|
| Code bản chạy thử | Claude Code | Viết `codebase/ai.py`, `tools.py`, `agent.py`, `api.py`, `deck.py`, `pptx_export.py`, giao diện `ui/`; luồng tải tài liệu → slide → quiz → tải về | Chạy `python run.py eval`, mở web thử luồng đầu–cuối, đọc diff, sửa lỗi khi chạy | Phạm Quốc Huy (lead, AI/Prompt, Tester); Trần Bảo Long (BE, FE) |
| Code bản chạy thử (mô-đun phụ) | Codex | Viết `exporters.py` (PDF quiz bằng `fpdf2`, giọng đọc bằng `edge-tts`), `ingest.py` (đọc PDF/DOCX/PPTX/TXT/MD, trích ảnh) và `tests/` | Chạy lại unit test, mở thử file PDF/MP3 xuất ra | Trần Bảo Long (BE, FE) |
| Prompt / thiết kế lời gọi mô hình | Claude Code | Soạn prompt sinh quiz/slide, prompt phân loại yêu cầu và gắn nhãn kiểm nguồn (`KHOP_NGUON` / `SAI_NGUON` / `THIEU_NGUON`); luồng hai model `claude-sonnet-5-5` (sinh) + `claude-haiku-5-5` (kiểm) | Người đọc output từng lượt `eval`, nhận ra nhóm lỗi (mã đoạn bị hạ nhầm, kiểm quá khắt) rồi quyết định sửa prompt/code; code kiểm cứng (đủ 4 phương án, đúng 1 đáp án, `segment_id` tồn tại) do người chốt | Phạm Quốc Huy |
| Đào data (viết script đếm, gợi ý nhãn) | Claude Code | Viết script `evidence/mine_preclass.py` đếm tỉ lệ sai lần đầu của `answers.csv` (ngày 28/11/2026, sau khi đã biết data — ghi rõ trong `evidence/data-mining.md`) | Người đọc từ điển cột và vài dòng đầu của `answers.csv` trước khi chạy; chưa đọc kỹ 30–50 dòng. Kiểm tay: ___ dòng, khớp ___ *(điền số thật)* | Trịnh Gia Huy (Eval, Data) |
| Rà câu hỏi phỏng vấn / khảo sát | *(điền nếu có dùng; không dùng thì ghi "không dùng")* | Chỉ rà câu dẫn dắt | Câu hỏi gửi người thật do nhóm quyết định; khảo sát n = 20 hợp lệ / 23 phiếu | Nguyễn Thành Tâm (BA) |
| Viết câu thử (benchmark) | Không dùng AI để viết (theo `data/DATA_CARD.md`: 15 câu `tu_viet` nhóm tự viết; 10 câu `nguoi_dung` lấy tình huống từ khảo sát, câu chữ nhóm viết) | — | Mỗi câu thử có `source`; câu thử AI viết được ghi rõ. Không xoá câu thất bại, không sửa `expected` cho khớp output | Trịnh Gia Huy (Eval, Data) |
| Sinh data `synthetic` | Không dùng AI sinh (theo `data/DATA_CARD.md`: nhóm tự tóm tắt, biên tập thủ công) | Kho `data/sources/segments.json`: 14 đoạn tóm tắt từ 3 buổi học (1, 4, 7), cài 1 đoạn bản cũ cố ý (`D01-S06`, 32K token) để đo phát hiện nguồn lỗi thời | Nhãn `synthetic` trong `data/DATA_CARD.md`. Seed: không áp dụng (viết tay/tóm tắt, không sinh ngẫu nhiên) · Trịnh Gia Huy và Phạm Quốc Huy kiểm tay 14/14 đoạn đúng kiến thức nền LLM / Prompting / RAG | Trịnh Gia Huy (Eval, Data) |
| Chấm cột `pass` bằng LLM | **Không dùng** | — | Cột `pass` do người viết code chấm tay theo `eval/metric_spec.yaml`. Người thứ hai chấm thử: **chưa làm** (xem `eval/README.md`) | Phạm Quốc Huy (Tester) |
| Rà soát đặc tả, tài liệu | Antigravity | Rà `spec.md`, hoàn thiện giao diện kiểm duyệt cũ (`ui/legacy/`), đồng bộ tài liệu dự án | Thành viên đọc lại, quyết định nội dung; `spec.md` §7 và `eval/metric_spec.yaml` không sửa sau CP2 | Nguyễn Thành Tâm (BA, CI/CD) |
| Slide, văn bản | Claude Code (cấu trúc, nháp); Antigravity (đồng bộ) | Dựng khung `demo-slides.pdf` / `slides/`, nháp tài liệu từ log chạy thật | Nhóm sửa nội dung, số liệu chỉ lấy từ `eval/run-*.csv`, `cost/simulate-*.csv`, `traces/`; số không có nguồn ghi *(tự ước tính)* | Cả nhóm |

## 3. AI trong sản phẩm (không phải công cụ làm bài)

- Gọi model thật ở `codebase/ai.py`: `claude-sonnet-5-5` sinh quiz/slide, `claude-haiku-5-5` phân loại yêu cầu và gắn nhãn kiểm nguồn. Token đọc từ `usage` của API, không ước lượng.
- Giọng đọc: `edge-tts` (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`).
- Quyết định cuối luôn là của người: sản phẩm chỉ lưu bản nháp ở `drafts/`, không tự xuất bản lên LMS.

## 4. Không dùng AI để

- Tạo người được phỏng vấn, trích dẫn, câu trả lời khảo sát.
- Sửa kết quả các lượt đã chạy (`eval/run-*.csv`, `cost/simulate-*.csv`, `traces/`), ngoài cột `pass` và `ghi_chu`.
- Chấm cột `pass` (không dùng LLM chấm).

## 5. Việc còn thiếu (nhóm điền trước khi nộp)

- Ô còn trống ở bảng trên: số dòng đã kiểm tay cho script đào data, và việc có dùng AI để rà câu hỏi khảo sát hay không. Repo không ghi hai thông tin này.
- Mỗi thành viên phải giải thích được phần có tên mình ở cột "Ai phụ trách".
