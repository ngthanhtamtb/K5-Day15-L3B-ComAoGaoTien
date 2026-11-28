---
name: slide-design
description: Quy tắc thiết kế slide của app (bảng màu, kiểu chữ, bố cục, ảnh trích từ tài liệu, giọng đọc). Dùng khi sửa codebase/deck.py, codebase/pptx_export.py hoặc prompt sinh slide trong codebase/agent.py.
---

# Thiết kế slide cho app A3

Nguồn sự thật: `codebase/deck.py` (HTML) và `codebase/pptx_export.py` (PPTX). Hai file dùng chung bảng màu `deck.THEMES`.

## Quy tắc
- Sân khấu cố định 1280×720 (16:9), co giãn bằng `transform: scale`; không dùng đơn vị theo viewport.
- Chữ: Be Vietnam Pro (hỗ trợ tiếng Việt), tiêu đề 52px/800, ý chính 29px; chữ dày đặc (>210 ký tự) tự hạ cỡ.
- Mỗi slide tối đa 3 ý, mỗi ý ≤ 16 từ; tiêu đề ≤ 8 từ; `tu_khoa` 1–3 từ làm nhãn nhỏ phía trên.
- Bố cục chọn bằng code (`deck.layout_of`): có ảnh → `media-r`/`media-l` luân phiên; không ảnh + ≥3 ý → `cards`; còn lại → `focus` (khung từ khoá).
- Bảng màu: mọi cặp chữ/nền tương phản ≥ 4.5:1; 4 bảng: Học thuật (mặc định), Ấm áp, Tối, Tối giản. Thêm bảng mới chỉ cần thêm vào `THEMES` đủ 12 khoá.
- Ảnh lấy từ tài liệu nạp (`ingest.extract_images`), gắn theo đoạn nguồn (`api._assign_images`), chú thích "Hình trích từ tài liệu · <mã đoạn>". Không bịa ảnh, không dùng ảnh ngoài tài liệu.
- Chuyển động nhẹ (≤ 0.65s), tôn trọng `prefers-reduced-motion`.
- Giọng đọc: lời thuyết trình 3–5 câu văn nói, không mã nguồn, không markdown; phụ đề chạy theo câu; thiếu file mp3 thì dùng giọng trình duyệt.
