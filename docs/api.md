# Hợp đồng API cho giao diện (`codebase/api.py`)

Chạy: `python -m uvicorn api:app --app-dir codebase --port 8000`. Biến môi trường: `CORS_ORIGINS` (mặc định `*`, khi deploy đặt origin thật). Bản nháp và kịch bản chỉ nằm trong bộ nhớ (tắt server là mất). **Không có endpoint xuất bản**: trạng thái cuối luôn là `cho_duyet`, giảng viên tự xuất bản ngoài hệ thống.

Mã đoạn dạng `D01-S02` (prototype ghi `DAY01-S02`: giao diện tự đổi khi hiển thị). Mọi lệnh gọi model trả thêm `trace` (xem cuối trang).

## Tương ứng màn hình của prototype → endpoint

| Màn prototype | Việc | Endpoint |
|---|---|---|
| 1 · Nhập bản nháp | danh sách buổi / ngày cập nhật ở cột phải | `GET /api/kho` |
| 1 · Nhập bản nháp | bấm "Bắt đầu đối chiếu" | `POST /api/scripts` `{buoi, noi_dung}` |
| 2 · Bảng rà soát | chi tiết một câu + "Đoạn nguồn trích dẫn" | trong `claims[i].nguon`; hoặc `GET /api/segments/{id}` |
| 2 · Bảng rà soát | Chấp nhận / Từ chối / Sửa từng câu | `POST /api/scripts/{id}/decisions` |
| 2 · Bảng rà soát | "Chấp nhận mọi câu Khớp nguồn chưa quyết" | `POST /api/scripts/{id}/accept-matching` |
| 2 · Bảng rà soát | "Gửi chờ duyệt" (bật khi hết câu chưa quyết) | `POST /api/scripts/{id}/submit` |
| 3 · Tạo slide | bấm "Tạo slide" | `POST /api/drafts` `{kind:"slide", buoi, script_id, so_luong, options}` |
| 4 · Kiểm từng slide | "Đạt" / "Cần sửa" + ghi chú | `POST /api/drafts/{id}/gate1` (`accept` / `reject` / `edit`, `note`) |
| 4 · Kiểm từng slide | dựng slide HTML + giọng đọc | `POST /api/drafts/{id}/build` |
| 4 · Kiểm từng slide | sửa trực tiếp, kiểm lại, đề xuất sửa | `POST /api/drafts/{id}/gate2` |
| 4 · Kiểm từng slide | gửi chờ duyệt | `POST /api/drafts/{id}/submit` |
| 5 · Kiểm từng câu quiz | như slide, `kind:"quiz"` (từ chủ đề hoặc `script_id`) | cùng các endpoint `/api/drafts…` |
| 5 · Quiz | tải PDF đề / đáp án | `GET /api/drafts/{id}/files/exam_pdf` · `answer_pdf` |
| Panel Agent verify | quy trình, token, chi phí | `trace` trong mỗi phản hồi, `traces` trong bản nháp / kịch bản |

## Kịch bản

`POST /api/scripts` → `{created, script}`. `script.claims[]` mỗi câu có: `index`, `noi_dung`, `nhan` (`KHOP_NGUON` / `SAI_NGUON` / `THIEU_NGUON` / `TU_CHOI`), `segment_id`, `ly_do`, `de_xuat_sua`, `nguon_cu`, `canh_bao_ma`, `nguon` (đoạn đầy đủ hoặc `null`), `quyet_dinh` (`chua_quyet` / `chap_nhan` / `tu_choi_cau` / `da_sua`). Kèm `tong_cau`, `da_quyet`, `dem_nhan`, `chen_chi_dan`.

- Câu chứa chỉ dẫn chèn ("bỏ qua bước duyệt", "[Ghi chú cho hệ thống: …]", xuất bản ngay…) bị **tách ra trước khi rà soát**, luôn gắn `TU_CHOI`, không thể chấp nhận (422) và không bao giờ vào slide. Các câu còn lại vẫn được rà soát bình thường.
- `decisions`: `{decisions:[{index, action:"accept|reject|edit|reset", noi_dung?}]}`. `edit` kiểm lại câu mới bằng cùng bộ gắn nhãn.
- `accept-matching` chỉ chấp nhận câu `KHOP_NGUON` chưa quyết; `SAI` / `THIEU` / `TU_CHOI` giữ nguyên để giảng viên tự quyết.
- `submit` trả 409 nếu còn câu `chua_quyet`.

## Bản nháp

`POST /api/drafts` có hai cách: từ chủ đề (`buoi`, `chu_de`) hoặc từ kịch bản (`buoi`, `script_id`; yêu cầu hết câu chưa quyết, chỉ dùng câu `chap_nhan` / `da_sua`). Phản hồi `{created, draft}` hoặc `{created:false, status, message}` khi hệ thống từ chối / thiếu nguồn (`thieu_nguon`, `hoi_lai`, `tu_choi`).

Các bước phải theo thứ tự cổng 1 → build → cổng 2 → submit; sai thứ tự trả 409. Mục sửa ở cổng 1 / 2 gộp lên mục gốc (khoá không gửi, vd `segment_id`, giữ nguyên); thiếu khoá bắt buộc trả 422.

## Nạp tài liệu thật

- `POST /api/kho/upload` `{filename, content_b64, title?, buoi?}` — `filename` đuôi `.pdf` / `.docx` / `.txt` / `.md` (≤ 5 MB), `content_b64` là nội dung file mã hoá base64. Trích chữ → cắt đoạn ~200–900 ký tự → mã `D{buoi}-S{nn}` (buổi tự chọn từ 10, 1–9 dành cho kho gốc) → lưu ở `data/uploads/segments.json` (không commit). Trả `{buoi, ten, so_doan, doan}`; lỗi định dạng / quá lớn / rỗng → 422 (thông báo tiếng Việt). Không gọi model, không tốn token.
- `DELETE /api/kho/{buoi}` — xoá tài liệu đã nạp (buổi ≥ 10; buổi 1–9 → 403; không có → 404).
- `GET /api/kho` thêm khoá `tai_len` (true với tài liệu nạp). Tài liệu nạp dùng được ở mọi endpoint như kho gốc (tra nguồn, sinh quiz / slide, rà soát).
- Bộ câu thử `eval` / `simulate` phải chạy trên kho gốc: đặt biến môi trường `A3_NO_UPLOADS=1` (bỏ qua `data/uploads/`). `eval/stability.py` tự đặt biến này.
- Tra nguồn là so khớp từ khoá (IDF, bỏ dấu), chưa dùng embedding; PDF dạng ảnh quét (không có lớp chữ) không trích được.

## Chưa làm / giới hạn

- `options` cho slide: `mau` ("AI20K chuẩn" | "Tối giản"), `ty_le` ("16:9" | "4:3"), `ghi_chu` (bool, hiện lời thuyết trình) **được áp dụng** khi dựng slide HTML (`exporters.render_slides`); giá trị lạ bị bỏ qua. Khoá khác (vd `quiz`) chỉ được lưu lại — giao diện dùng `quiz` để tạo thêm một bản nháp quiz riêng.
- Quiz đi kèm slide là một bản nháp riêng (`kind:"quiz"`), không tự sinh cùng lúc.
- Lệnh gọi model được tuần tự hoá bằng khoá (trace dùng biến toàn cục), nên nhiều người dùng cùng lúc phải xếp hàng. Rà soát kịch bản dài (30–40 câu) chưa được đo thời gian.
- Chi phí trong `trace` tính theo giá niêm yết BTC; chi thật qua proxy cao hơn khoảng 6,5 lần (`cost/cost-estimate.md` §5).
- Không có đăng nhập: bất kỳ ai gọi được API đều đọc / sửa mọi bản nháp.

## `trace`

`{nhan, model_calls, tool_calls, tokens_in, tokens_out, models, errors, chi_phi_usd_niem_yet, cac_buoc:[{loai, ten, model, tokens_in, tokens_out, latency_s, loi}]}`. Dùng cho panel "Agent verify" (quy trình đã chạy, chi phí và trace).
