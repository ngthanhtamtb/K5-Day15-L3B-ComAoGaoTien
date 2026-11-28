# Báo cáo đánh giá — lượt 1 → cải tiến → lượt 2

> Cùng bộ câu thử (`eval/benchmark.csv`, 25 câu), cùng cách chấm (`eval/metric_spec.yaml`). Cột `pass` do một người (người viết code) chấm theo `pass_criterion`; **chưa có người thứ hai chấm thử** (xem `eval/README.md`).

## 1. Kết quả

| Lượt | Run ID | Đạt / tổng | % | thuong | kho | tu_choi | So với chuẩn "đạt" |
|---|---|---|---|---|---|---|---|
| 1 | `run-1@20261127-233321` | 20/25 | 80% | 6/8 | 11/14 | 3/3 | Chưa: tổng ≥70% và tu_choi 100% đạt, nhưng `trich_dung_nguon` < 100% (B05) |
| *(trung gian)* | `run-2@20261127-234248` | 22/25 | 88% | 6/8 | 13/14 | 3/3 | Chưa — 2 câu lỗi kỹ thuật (B02, B03); giữ nguyên, không sửa tay |
| *(trung gian)* | `run-3@20261127-235723` | 23/25 | 92% | 7/8 | 13/14 | 3/3 | Chưa: B15 có nhãn KHOP_NGUON, B18 sai nhãn |
| **2** | `run-4@20261128-001420` | **25/25** | **100%** | 8/8 | 14/14 | 3/3 | Đạt cả ba vế (xem lưu ý ở mục 4) |

Chuẩn "đạt" (`spec.md` §7): ≥70% tổng câu qua, **và** 100% câu `tu_choi` qua, **và** `trich_dung_nguon` = 100%.
Kết quả từng câu: `eval/run-1.csv` … `eval/run-4.csv`. Trace: `traces/run-N.jsonl`.

## 2. Lỗi lượt 1 — gom thành nhóm có tên

| Nhóm lỗi | Số câu | Câu |
|---|---|---|
| **Mã đoạn bị hạ nhầm thành THIEU_NGUON** (model nhận định đúng nhưng trả mã dạng nhiều mã / có ngoặc, bộ kiểm hạ nhãn) | 4 | B12, B13, B14, B15 |
| **Bịa khẳng định / kiểm quá khắt** (tự thêm khẳng định lấy từ đoạn nguồn; coi câu tóm tắt gọn là sai) | 1 | B05 (và lỗi ẩn ở B16: trích khẳng định không có trong input) |

**≥3 lỗi cụ thể:**

| Câu | Input (rút gọn) | Output (rút gọn) | Vì sao sai |
|---|---|---|---|
| B13 | `[DUYET_QUIZ]` Câu 1: kỹ thuật nào yêu cầu model trình bày các bước suy luận? … **Đáp án: A** | `THIEU_NGUON` (lý do ghi đáp án đúng là B) | Nhãn cần `SAI_NGUON · D04-Q01`. Model trả mã không qua kiểm nên bị hạ nhãn: một đáp án sai bị báo là "thiếu nguồn", không cảnh báo giảng viên |
| B15 | `[DUYET_QUIZ]` Câu 3: phát biểu nào đúng về RAG? A… B. RAG không đổi trọng số… **Đáp án: A** | `THIEU_NGUON` (lý do nêu phương án B cũng đúng) | Nhãn cần `SAI_NGUON · D07-S04` (câu có 2 đáp án đúng). Cùng nguyên nhân: mã đoạn bị hạ |
| B05 | `[DUYET_KICH_BAN]` LLM sinh văn bản theo cách tự hồi quy… (câu đúng) | `SAI_NGUON · D01-S01` + 3 khẳng định bịa lấy từ đoạn nguồn khác | Cần `KHOP_NGUON · D01-S01`. Model quá khắt (câu tóm tắt gọn bị coi sai) và tự thêm khẳng định có mã ngoài tập mong đợi → vi phạm `trich_dung_nguon` |
| B12 | `[DUYET_KICH_BAN]` RAG giúp giảm bịa… [nguồn: D01-S02] | `THIEU_NGUON` + cảnh báo mã D01-S02 | Cần `KHOP_NGUON · D07-S01` kèm cảnh báo. Mã ghi sẵn sai bị coi là "không có nguồn" |

## 3. Một lần cải tiến (và các sửa nối tiếp)

- **Nhắm vào nhóm lỗi:** mã đoạn bị hạ nhầm — vì sao là nhóm **đau nhất với người dùng**: B13, B15 là *đáp án sai lọt qua* (báo THIEU thay vì SAI) — đúng thứ giảng viên sợ nhất (đáp án sai tới 700+ học viên).
- **Đã sửa gì** (`codebase/agent.py`): lấy mã đoạn hợp lệ đầu tiên thay vì hạ nhãn; code lọc khẳng định không có trong input (≥60% từ khoá phải nằm trong nội dung đang kiểm); prompt: câu nói gọn hơn nguồn vẫn là KHOP, mã ghi sẵn sai mà nội dung có nguồn khác thì KHOP kèm cảnh báo.
- **Sửa nối tiếp** (từ lỗi của lượt trung gian, ghi ở `spec.md` §10):
  - `run-2`: B02, B03 không có output vì Sonnet dùng hết 4096 token cho phần "suy nghĩ" (`stop_reason=max_tokens`) → `ai.py` tăng ngân sách và gọi lại khi bị cắt. B04 trích D01-S01 (chỉ nhắc thoáng) → `tools.py` ưu tiên đoạn có tiêu đề khớp chủ đề.
  - `run-3`: B18 do model viết sai chính tả nhãn (KHOP_NGUAN) → chuẩn hoá nhãn theo tiền tố. B15 do model tách một câu trắc nghiệm thành 4 khẳng định → gộp thành một với nhãn nặng nhất. B05 có cảnh báo chèn chỉ dẫn sai (cờ model chập chờn) → phát hiện bằng mẫu câu lệnh rõ ràng.
  - Sau `run-4` (lỗi tìm thấy khi thử giao diện, không phải lỗi của bộ câu thử): cổng 2 gắn THIEU_NGUON thay vì SAI_NGUON khi một slide được sửa sai về context window, vì truy vấn cả khối văn bản làm loãng từ khoá và đoạn D01-S04 không lọt vào nguồn → `agent.py` tra thêm theo từng câu (`_gather_multi`). Chạy lại ca đó 3/3 ra SAI_NGUON · D01-S04.
  - `run-5`: B13 trượt do model trả khẳng định lạc đề (nói về một doanh nghiệp không có trong đầu vào lẫn kho). Chạy lại riêng 4/4 đúng; mã để lọt vì nhánh dự phòng `grounded or raw` → bỏ nhánh này, hỏi lại model một lần khi mọi khẳng định lạc đề; chuẩn hoá `y_chinh` khi model trả dict (B04).
- **Kết quả:** nhóm lỗi mã đoạn bị hạ nhầm 0/4 → 4/4 · tổng 80% → 100% (`run-4`); sau các sửa nối tiếp: `run-5` 24/25 (96%), `run-6` 25/25 (100%).
- **Câu nào tệ đi sau khi sửa:** so với lượt 1, không câu nào. Trong lượt trung gian có câu tệ đi tạm thời: B02, B03 (lỗi kỹ thuật, `run-2`), B04 (`run-2`), B15 và B18 (`run-3`) — đều đã sửa và qua ở `run-4`.

## 4. Còn lại

- **100% có thể lạc quan:** có 4 lượt chạy lặp trên cùng bộ 25 câu và mỗi lần sửa nhắm vào câu vừa trượt, nên có rủi ro sửa theo bộ câu. Chưa kiểm trên câu ngoài bộ; câu giám khảo đưa tại chỗ có thể trượt. Các sửa đều là quy tắc chung (chuẩn hoá nhãn, lọc khẳng định bịa, ngân sách token), không so khớp input của bộ câu thử.
- **Model chập chờn:** cùng input có thể ra khác nhau (vd cờ chèn chỉ dẫn ở B05 `run-3`; B13 ở `run-5` ra nội dung lạc đề nhưng `run-6` và 4 lần chạy riêng đều đúng). Hai lượt liên tiếp `run-5` (96%) và `run-6` (100%) trên cùng mã cho kết quả khác nhau một câu, nên con số 100% không nên đọc là chắc chắn; cần chạy mỗi câu ≥3 lần để đo độ ổn định (chưa làm).
- **Chấm một người:** cột `pass` do người viết code chấm; metric `ban_sinh_dat` (mục d) và `tu_choi_dung` chấm bằng người. Cần người thứ hai chấm thử 5 output.
- **Kho nguồn nhỏ:** 14 đoạn do nhóm tự viết (`synthetic`); chưa kiểm ở tài liệu thật 20–80 trang. Retrieval so khớp từ khoá, chưa dùng embedding.
- Nếu có thêm 1 tuần: nạp tài liệu thật của khoá, thêm bộ câu thử ngoài bộ để kiểm khái quát, chạy mỗi câu nhiều lần, thêm chỉ số về học (nếu hướng lớp học kiểu mới), người thứ hai chấm 10–15 output.
