# Data card — dữ liệu bản chạy thử dùng

> Một trang. Không commit nguyên tài liệu khoá, dữ liệu cá nhân thật hay nguyên file data BTC cấp.

## Dataset 1 · Kho đoạn tài liệu gốc (`data/sources/segments.json`)

| | |
|---|---|
| Dùng để làm gì | Nguồn cho `search_sources` / `get_segment`. Là căn cứ để **sinh** câu quiz và kịch bản slide, và để **kiểm** ở cả 2 cổng duyệt; là "nguồn sự thật" để chấm `trich_dung_nguon` |
| Từ đâu | Nhóm tự viết lại ngắn các khái niệm của buổi 1 (nền tảng LLM), buổi 4 (prompt engineering), buổi 7 (RAG). Không chép nguyên slide / transcript |
| Xử lý những bước gì | Mỗi khái niệm viết thành 1 đoạn 1–4 câu · gắn `segment_id` dạng `D<buổi>-S<số>` (câu hỏi có sẵn trong ngân hàng: `D<buổi>-Q<số>`) · gắn `updated_date` |
| Số dòng / số đoạn | 14 đoạn: buổi 1 = 6 (gồm 1 đoạn bản cũ), buổi 4 = 4 (gồm 1 câu hỏi trắc nghiệm mẫu), buổi 7 = 4 |
| Phiên bản / ngày lấy | v1 · 27/11/2026 |
| Nhãn | `synthetic` |
| Giới hạn | Rất nhỏ so với tài liệu thật (một bài 20–80 trang theo khảo sát). Các con số lab (chunk 500, top-k 5, context 128K) là **giá trị nhóm đặt cho kho thử**, không trích từ tài liệu khoá. `D01-S06` cố ý là bản cũ (03/2024) mâu thuẫn `D01-S04` để thử ca "nguồn lỗi thời". Chỉ tiếng Việt, chỉ chủ đề LLM/RAG; không có buổi 9 (dùng cho câu thử B21) |

**Cách sinh:** viết tay, không dùng seed. Người kiểm: __ (điền tên), đã kiểm tay __/14 đoạn đúng kiến thức.

## Dataset 2 · Bộ câu thử (`eval/benchmark.csv`)

| | |
|---|---|
| Dùng để làm gì | Chạy `python run.py eval`, chấm theo `eval/metric_spec.yaml` |
| Từ đâu | 15 câu nhóm tự viết theo 4 lớp chỗ khó ở `spec.md` §5 (`tu_viet`) · 10 câu dựng từ phần việc tốn công mà người trả lời khảo sát nêu (`nguoi_dung: khảo sát …`, ghi rõ phiếu / câu hỏi) |
| Xử lý những bước gì | Mỗi câu mở đầu bằng chế độ: `[TAO_QUIZ]` / `[TAO_SLIDE]` (sinh) · `[DUYET_KICH_BAN]` / `[DUYET_QUIZ]` (cổng 1) · `[DUYET_CUOI]` (cổng 2, phần giảng viên đã sửa) · không tag (yêu cầu ngoài phạm vi). `expected` = nhãn + mã đoạn trong Dataset 1 |
| Số dòng / số đoạn | 25 câu: `thuong` 8 · `kho` 14 · `tu_choi` 3. Theo chế độ: sinh 7 (B01–B04, B21, B22, B25) · cổng 1 kịch bản 8 (B05–B12) · cổng 1 quiz 4 (B13–B16) · cổng 2 4 (B17–B20) · tấn công / ngoài phạm vi 2 (B23, B24) |
| Phiên bản / ngày lấy | v2 · 27/11/2026 — đổi lát cắt từ "chỉ kiểm duyệt kịch bản" sang "tạo quiz + slide có giọng thuyết trình, 2 cổng duyệt" (chốt tại CP2, không sửa `expected` sau đó) |
| Nhãn | `synthetic` — kể cả 10 câu `nguoi_dung`: **tình huống** lấy từ khảo sát, **câu chữ** do nhóm viết |
| Giới hạn | Chỉ đo lớp văn bản (nội dung quiz, kịch bản, nhãn); file PDF, slide và audio không nằm trong bộ câu thử, kiểm tay khi demo. Lỗi do nhóm cố ý cài nên có thể dễ thấy hơn lỗi thật. Câu sinh (B01–B04) chấm đúng/sai nội dung cần người |

**Data tự dựng không phải bằng chứng pain.**

## Dataset 3 · Khảo sát người làm bài giảng (`team_docs/KhaoSat.xlsx`)

| | |
|---|---|
| Dùng để làm gì | Gợi tình huống cho bộ câu thử (B03, B04, B10–B15, B17, B20) và phần `why` của metric; bằng chứng pain ghi ở `evidence/` |
| Từ đâu | Google Form nhóm gửi trong lớp chiều 27/11/2026 (17:26–18:32) |
| Xử lý những bước gì | Loại 3 phiếu (2 phiếu tháng qua kiểm 0 bài · 1 vai "Sinh viên") theo quy tắc ghi ở `evidence/survey/questions.md` · bỏ cột liên hệ khỏi repo · chỉ dùng số tổng hợp và trích ngắn câu trả lời; log ẩn danh: `evidence/survey/results.csv` |
| Số dòng / số đoạn | 23 phiếu, **20 hợp lệ**: giảng viên chuyên môn 10 · người soạn 5 · biên tập/sản xuất 4 · trợ giảng 1 |
| Phiên bản / ngày lấy | Xuất ngày 28/11/2026 (bản cập nhật; bản đầu 27/11 có 8 phiếu) |
| Nhãn | thật |
| Giới hạn | **n = 20, đạt ngưỡng 20 của khảo sát.** Trộn nhiều vai. Khảo sát hỏi về **kiểm tra** bài giảng, chưa hỏi về việc soạn quiz / làm slide hay nhu cầu giọng thuyết trình. Mức phiền trung bình 2,9/5, lo sót lỗi 2,8/5 — pain mức vừa; 11/20 người kiểm xong trong 30 phút trở xuống |

Số chính (20 phiếu hợp lệ): duyệt ≥6 bài/tháng 5/20 · bài 20–40 trang 9/20, 41–80 trang 4/20 · thời gian kiểm 1 bài: dưới 15 phút 4, 15–30 phút 7, 31–60 phút 4, 1–2 tiếng 2, trên 2 tiếng 1, không nhớ 2 · cách kiểm: trí nhớ 14/20, nguồn ghi sẵn 10/20, mở tài liệu so 9/20 · đã dùng AI hỗ trợ: 11/20.
