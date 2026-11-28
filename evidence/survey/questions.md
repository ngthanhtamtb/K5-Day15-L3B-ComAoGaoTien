# Khảo sát người làm bài giảng — bộ câu hỏi và log

Form Google, mở chiều 27/11/2026 (phiếu đầu 17:26, phiếu cuối 18:32). Kênh gửi: *(nhóm điền: lớp, nhóm chat…)*. Không thu tên; câu liên hệ là tự nguyện và **không đưa vào repo**.

| # | Câu hỏi | Kiểu trả lời |
|---|---|---|
| 1 | Thầy/cô/anh/chị làm vai trò nào trong việc xây dựng bài giảng? | Chọn một: giảng viên · người soạn · biên tập / sản xuất · sinh viên |
| 2 | Tháng vừa rồi đã kiểm tra hoặc duyệt bao nhiêu bài giảng? | 0 · 1–2 · 3–5 · 6 trở lên |
| 3 | Bài giảng lần đó có khoảng bao nhiêu trang? | Dưới 20 · 20–40 · 41–80 · Không nhớ |
| 4 | Làm thế nào để biết nội dung bài giảng có đúng với tài liệu gốc? | Chọn nhiều |
| 5 | Lần đó mất khoảng bao lâu để kiểm tra? | Dưới 15 phút · 15–30 · 31–60 · 1–2 tiếng · Trên 2 tiếng · Không nhớ |
| 6 | Phần nào mất nhiều công nhất? | Viết ngắn |
| 7 | Hiện có dùng công cụ hay mẹo gì để kiểm tra đỡ vất vả không? | Viết ngắn |
| 8 | Vì sao chọn cách đó? | Viết ngắn |
| 9 | Việc kiểm tra bài giảng với tài liệu gốc phiền tới mức nào? | 1–5 |
| 10 | Lo bài giảng bị sót lỗi tới mức nào? | 1–5 |
| 11 | Đồng ý hẹn 10–15 phút để hỏi kỹ hơn không? | Có / Không |

## Log từng câu trả lời

`results.csv` — 23 phiếu (phiếu 23 thêm sau cùng dù trong file gốc nằm giữa phiếu 15 và 16, để giữ nguyên số thứ tự các phiếu đã trích dẫn; `stt` không theo giờ), đã xoá cột liên hệ và giờ phút. Cột `hop_le` = 0 kèm lý do loại. Bản gốc có thông tin liên hệ giữ ở máy nhóm, **không commit**.

## Quy tắc loại phiếu (áp dụng cho mọi phiếu)

1. Vai không phải giảng viên / người soạn / biên tập: loại (người dùng của lát cắt).
2. Thiếu vai: loại (không xác nhận được đúng người dùng).
3. Tháng vừa rồi kiểm / duyệt 0 bài: loại khỏi số tính (câu hỏi về hành vi đã xảy ra, họ chưa có hành vi).
## Hạn chế

- Khảo sát hỏi về việc **kiểm tra** bài giảng. Chưa hỏi việc **soạn** quiz và làm slide, nên chưa đo trực tiếp nhu cầu "tạo quiz + slide có giọng thuyết trình".
- Chưa xác minh từng người trả lời có ngoài nhóm hay không: nhóm tự xác nhận.
