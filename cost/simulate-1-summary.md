# Tóm tắt mô phỏng simulate-1@20261128-012643

Do `python run.py simulate` sinh ra — không sửa tay. Chép bảng sang `cost/cost-estimate.md`.

| Persona | Số phiên mô phỏng | Lượt hỏi / phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Gọi công cụ / phiên |
|---|---:|---:|---:|---:|---:|---:|
| dung_it | 35 | 2 | 4680 | 6789 | 4.5 | 13.2 |
| dung_vua | 35 | 3 | 6880 | 11580 | 6.6 | 18.6 |
| dung_nhieu | 23 | 4 | 9129 | 14058 | 9.0 | 26.2 |

Tỉ lệ đạt dùng để tính: 25/25 (100%) — lượt run-4@20261128-001420

- Tỉ lệ đạt lấy từ lượt nhóm chọn: eval/run-4.csv (--rate-from).

| Model (giá) | Chi phí / phiên | Chi phí / task thành công | Chi phí / câu hỏi đạt | Chi phí / tháng — thấp (5 người) | Chi phí / tháng — cơ sở (8 người) | Chi phí / tháng — cao (20 người) | Chi phí / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Thực đo — mỗi model giá riêng** (claude-haiku-5-5 + claude-sonnet-5-5) | $0.0219 | $0.0219 | $0.0076 | $0.6392 | $1.02 | $2.56 | $0.1278 |
| claude-haiku-5-5 (vào 0.1 · ra 0.5 $/1M) — nếu MỌI token tính giá model này | $0.0059 | $0.0059 | $0.0020 | $0.1522 | $0.2436 | $0.6089 | $0.0304 |
| claude-sonnet-5-5 (vào 2.0 · ra 10.0 $/1M) — nếu MỌI token tính giá model này | $0.1171 | $0.1171 | $0.0408 | $3.04 | $4.87 | $12.18 | $0.6089 |
| claude-opus-5-5 (vào 4.0 · ra 20.0 $/1M) — nếu MỌI token tính giá model này | $0.2342 | $0.2342 | $0.0816 | $6.09 | $9.74 | $24.36 | $1.22 |

- Chi phí / task thành công = chi phí / phiên ÷ tỉ lệ đạt. Chi phí / câu hỏi đạt = chi phí / phiên ÷ số lượt hỏi trung bình mỗi phiên (2.9) ÷ tỉ lệ đạt — tỉ lệ đạt đo theo từng câu thử.
- Token đo trên model: claude-haiku-5-5, claude-sonnet-5-5. Giá tính theo từng model trong bảng — model khác bộ tách token thì số token thật có thể lệch; ghi rõ "đo trên model X, tính giá model Y" trong cost/cost-estimate.md.
- Phiên lỗi (không tính vào trung bình): 7/100.
