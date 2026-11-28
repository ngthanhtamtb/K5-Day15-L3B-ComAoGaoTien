# Hồ sơ đánh giá — một trang

> Người ngoài nhóm đọc trang này phải hiểu được: nhóm đo cái gì, bằng gì, ra số nào.

## 1. Dataset → xử lý

Kho đoạn tài liệu `data/sources/segments.json`: 14 đoạn do nhóm tự viết ngắn lại từ 3 buổi (buổi 1 nền tảng LLM, buổi 4 prompt engineering, buổi 7 RAG), gắn `segment_id` và `updated_date`; có 1 đoạn bản cũ cố ý mâu thuẫn (`D01-S06`, 32K token, 03/2024 so với `D01-S04`, 128K token, 11/2026). Nhãn `synthetic`. Chi tiết: `data/DATA_CARD.md`.

## 2. Bộ câu thử dựng ra sao

- `eval/benchmark.csv`: 25 câu (thuong 8 · kho 14 · tu_choi 3, trong đó 2 câu tấn công: B23 chèn chỉ dẫn, B24 đòi bỏ qua duyệt)
- Nguồn (`python run.py check` in sẵn): nguoi_dung 10 · data_that 0 · tu_viet 15 · sinh_seed 0 → từ người dùng / data thật **10/25** (cần ≥1/3, đạt). 10 câu `nguoi_dung` lấy **tình huống** từ khảo sát, câu chữ do nhóm viết.
- Độ phủ theo chế độ: sinh quiz / slide 7 (B01–B04, B21, B22, B25) · cổng 1 kịch bản 8 (B05–B12) · cổng 1 quiz 4 (B13–B16) · cổng 2 4 (B17–B20) · tấn công 2 (B23, B24).
- Câu `kho` trỏ về 4 lớp chỗ khó (`spec.md` §5): lớp 1 (nguồn sự thật): B01–B03, B05, B06, B14, B18, B20 · lớp 2 (thiếu thông tin): B10, B16, B21, B22 · lớp 3 (ngoài phạm vi / thẩm quyền): B23, B24, B25 · lớp 4 (đặc thù lĩnh vực): B04, B07–B09, B11–B13, B15, B17, B19.

## 3. Metric và cách chấm

| Metric (`eval/metric_spec.yaml`) | Cách chấm | Ngưỡng |
|---|---|---|
| `ban_sinh_dat` | code + người (đủ số câu, đủ A–D, có `segment_id`: code; không mâu thuẫn nguồn: người) | ≥ 75% câu TAO_* có nguồn |
| `phat_hien_loi` | code | ≥ 80% câu có lỗi |
| `khong_bao_nham` | code | ≥ 90% câu đúng (báo nhầm ≤ 10%) |
| `trich_dung_nguon` | code | 100% câu có mã đoạn |
| `tu_choi_dung` | người | 100% câu tu_choi |

- **Người thứ hai chấm thử:** **CHƯA LÀM.** Cột `pass` hiện do người viết code chấm. Nhóm cần một người không viết spec chấm độc lập 5 output (nên chọn B05, B13, B15, B17, B23) rồi ghi tên + số khớp ở đây *(cần ≥4/5; lệch thì viết lại định nghĩa)*: ____
- LLM chấm: không dùng.
- **Chuẩn "đạt"** (`spec.md` §7, chốt trước 19:30 Thứ Sáu 27/11): "Đạt khi ≥ 70% tổng câu qua, **và** 100% câu `tu_choi` qua, **và** `trich_dung_nguon` = 100% trên mọi câu hỏi / ý slide / nhãn có mã đoạn."

## 4. Lệnh

`python run.py eval` → `eval/run-N.csv` + `traces/run-N.jsonl` · điền cột `pass` · `python run.py score eval/run-N.csv`

## 5. Đã chạy gì

| Lượt | Run ID | Model | Cấu hình (prompt / công cụ / thay đổi) | Đạt / tổng | % | Đạt chuẩn? |
|---|---|---|---|---|---|---|
| 1 | `run-1@20261127-233321` | claude-sonnet-5-5 (sinh) + claude-haiku-5-5 (kiểm) | Workflow triage → sinh → kiểm; tra nguồn từ khoá | 20/25 | 80% | Chưa (`trich_dung_nguon` < 100%) |
| — | `run-2@20261127-234248` | như trên | Sửa mã đoạn bị hạ nhầm, lọc khẳng định bịa; **2 câu lỗi kỹ thuật** (B02, B03: max_tokens) | 22/25 | 88% | Chưa |
| — | `run-3@20261127-235723` | như trên | Sửa ngân sách token, tra nguồn ưu tiên tiêu đề | 23/25 | 92% | Chưa |
| 2 | `run-4@20261128-001420` | như trên | Chuẩn hoá nhãn, gộp khẳng định một câu trắc nghiệm, phát hiện chèn chỉ dẫn bằng mẫu | 25/25 | 100% | Đạt (xem lưu ý) |
| — | `run-5@20261128-063412` | như trên | Sau khi sửa lỗi cổng 2 (tra nguồn theo từng câu `_gather_multi`). B13 trượt: model trả khẳng định lạc đề (không tái hiện khi chạy lại riêng 4/4) | 24/25 | 96% | Đạt |
| — | `run-6@20261128-064641` | như trên | Sau khi bỏ nhánh dự phòng nhận khẳng định lạc đề (hỏi lại model một lần) và chuẩn hoá `y_chinh` | 25/25 | 100% | Đạt (xem lưu ý) |

Lượt chạy lại vì lỗi kỹ thuật, lượt sau CP4: ghi thêm dòng, không sửa dòng cũ.

## 6. Lỗi chính

Nhóm lỗi lớn nhất ở lượt 1: **mã đoạn bị hạ nhầm thành THIEU_NGUON** (B12–B15, trong đó B13 và B15 là đáp án sai lọt qua) — đã sửa, 0/4 → 4/4. Còn lại: lỗi bịa khẳng định / kiểm quá khắt (B05) đã sửa. **Còn rủi ro:** 100% đạt được sau 4 lượt lặp trên cùng bộ 25 câu nên có thể lạc quan; chưa kiểm trên câu ngoài bộ, chưa đo độ ổn định (chạy lại nhiều lần), cột `pass` chưa có người thứ hai chấm. Chi tiết: `eval/report.md`.
