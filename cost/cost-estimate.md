# Chi phí khi dùng thật

> Số trong bảng không điền tay: lấy từ `cost/simulate-1-summary.md` (do `python run.py simulate --rate-from eval/run-4.csv` sinh ra). Giá tính theo **giá niêm yết gói trả phí** của bảng giá BTC, không phải số tiền thật đã trả qua proxy khi build (xem mục 5).

## 1. Đầu vào

- **Persona** (`cost/personas.yaml`): 3 kiểu, tỉ lệ và số bài / tháng lấy từ khảo sát n = 18 hợp lệ tại lúc chạy mô phỏng (`evidence/survey/results.csv`, câu 2). Sau đó phiếu 20 được bổ sung vai và thêm phiếu 23, khảo sát thành n = 20 (nhóm 1–2 bài: 7/20 thay vì 6/18; 3–5 bài: 8/20 thay vì 7/18); tỉ lệ lệch khoảng 2–4 điểm phần trăm, không chạy lại mô phỏng:
  - `dung_it` 33% (6/18) · 2 phiên / người / tháng · 2 lượt hỏi / phiên
  - `dung_vua` 39% (7/18) · 4 phiên / người / tháng · 3 lượt hỏi / phiên
  - `dung_nhieu` 28% (5/18) · 8 phiên / người / tháng · 4 lượt hỏi / phiên
  - Số lượt hỏi / phiên và 8 phiên của nhóm nhiều: *(tự ước tính)*.
- **Số người dùng thật** 3 kịch bản: thấp 5 · cơ sở 8 · cao 20. Nguồn: `spec.md` §2 "khoảng 5–8 giảng viên + đội sản xuất" *(tự ước tính, chưa có số đếm thật)*; mức cao 20 là mở rộng sang nhiều bộ môn *(tự ước tính)*.
- **Giá** (USD / 1 triệu token, bảng BTC `further-reading/model-prices.md`, xem 25/11/2026, nguồn https://platform.claude.com/docs/en/about-claude/pricing):
  - Claude Haiku 5.5: vào 0,10 · ra 0,50
  - Claude Sonnet 5.5: vào 2,00 · ra 10,00
  - Claude Opus 5.5: vào 4,00 · ra 20,00 (chỉ để so sánh, hệ thống không dùng)
- **Tỉ lệ đạt** dùng để tính: 25/25 (100%) — lượt `run-4@20261128-001420`. Lưu ý: 100% đạt được sau 4 lượt lặp trên cùng bộ câu nên có thể lạc quan (xem `eval/report.md`); nếu tỉ lệ đạt thật thấp hơn, chi phí / task thành công tăng theo 1 / tỉ lệ đạt (ví dụ 80% → ×1,25).
- Token **đo trên** claude-haiku-5-5 (phân loại đầu vào, kiểm nhãn) và claude-sonnet-5-5 (sinh quiz / kịch bản); **tính giá** từng model theo bảng giá riêng của model đó.

## 2. Kết quả mô phỏng

Lượt mô phỏng: `cost/simulate-1.csv` · run ID `simulate-1@20261128-012643` · 100 phiên chạy, **93 phiên hợp lệ** (đủ mức tối thiểu 50) · seed 42.

**7/100 phiên lỗi và bị loại khỏi trung bình** (gồm S077 và 5 phiên cuối S096–S100): proxy trả `HTTP 403 rate_limit_error` ("Try again in N seconds"); `ai.py` chỉ thử lại với 429/5xx nên không thử lại các lỗi này. Đây là lỗi giới hạn tốc độ của nhà cung cấp, không phải lỗi logic hay hết tiền. Nhóm chấp nhận 93 phiên, không chạy lại. Nếu dùng thật cần thêm retry cho 403 hoặc giãn nhịp gọi.

| Persona | Số phiên hợp lệ | Lượt hỏi / phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Gọi công cụ / phiên |
|---|---:|---:|---:|---:|---:|---:|
| dung_it | 35 | 2 | 4.680 | 6.789 | 4,5 | 13,2 |
| dung_vua | 35 | 3 | 6.880 | 11.580 | 6,6 | 18,6 |
| dung_nhieu | 23 | 4 | 9.129 | 14.058 | 9,0 | 26,2 |

| Model (giá) | Chi phí / phiên | Chi phí / task thành công | Chi phí / câu hỏi đạt | / tháng — thấp (5 người) | / tháng — cơ sở (8 người) | / tháng — cao (20 người) | / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Thực đo: mỗi model giá riêng** (Haiku 5.5 + Sonnet 5.5, cấu hình đang dùng) | $0,0219 | $0,0219 | $0,0076 | $0,64 | $1,02 | $2,56 | $0,128 |
| Nếu MỌI token tính giá Haiku 5.5 | $0,0059 | $0,0059 | $0,0020 | $0,15 | $0,24 | $0,61 | $0,030 |
| Nếu MỌI token tính giá Sonnet 5.5 | $0,1171 | $0,1171 | $0,0408 | $3,04 | $4,87 | $12,18 | $0,609 |
| Nếu MỌI token tính giá Opus 5.5 | $0,2342 | $0,2342 | $0,0816 | $6,09 | $9,74 | $24,36 | $1,22 |

Chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt (ở đây 100%, nên bằng chi phí / phiên). **Không coi 100% là chắc chắn**, xem mục 1.

## 3. So với impact

- Impact / người / tháng (`spec.md` §2): ~96 giờ-người / tháng cho ~8 người, tức ~12 giờ / người / tháng *(tự ước tính; khảo sát chỉ xác nhận thời gian kiểm, chưa xác nhận thời gian soạn)*.
- Chi phí / người / tháng (cơ sở, Haiku + Sonnet theo giá niêm yết): **$0,128**. Cả nhóm 8 người: ~$1,02 / tháng.
- **Kết luận một dòng:** chi phí model ~$0,13 / người / tháng, nhỏ hơn nhiều so với ~12 giờ công tiết kiệm được ước tính, nên đáng làm nếu impact ước tính đúng. Ngay cả khi nhân 6,5 theo giá thật qua proxy (~$0,83 / người / tháng, mục 5) vẫn nhỏ so với giờ công. Chưa tính giờ công người duyệt (2 cổng duyệt vẫn do giảng viên làm).

## 4. Hai mức model: chọn gì

| Cấu hình | Chi phí / phiên | Ghi chú |
|---|---:|---|
| Haiku + Sonnet (đang dùng) | $0,0219 | Sonnet sinh nội dung, Haiku phân loại và kiểm nhãn |
| Chỉ Sonnet cho mọi bước | ~$0,117 | Đắt gấp ~5,3 lần, chưa chứng minh tốt hơn ở bước kiểm |

Giữ Haiku cho bước kiểm vì nó là cần gạt rẻ nhất. Chưa đo tác động tới độ chính xác nếu hạ Sonnet xuống Haiku ở bước sinh.

## 5. Chi thật qua proxy so với giá niêm yết

Trong lúc build, nhóm trả qua một proxy trung gian (`api.fableaiapi.com`). Bảng điều khiển nhà cung cấp cho thấy chi thật **$17,41 / 502 request ≈ $0,0347 / request**, trong khi cùng lượng token tính theo giá niêm yết BTC chỉ khoảng $0,005 / request: **cao hơn khoảng 6,5 lần**. Số trong mục 2 và 3 dùng giá niêm yết như đề yêu cầu; nếu triển khai qua kênh tính giá như proxy này, nhân chi phí với ~6,5 (ví dụ $0,128 → ~$0,83 / người / tháng; cả nhóm 8 người ~$6,6 / tháng). Số 6,5 là ước tính của nhóm từ một lần đối chiếu, chưa được kiểm lại.

## 6. Chưa tính

- Hosting, lưu trữ, giờ công người duyệt.
- edge-tts miễn phí nhưng không có cam kết dịch vụ; xuất PDF / HTML chạy cục bộ, không tốn token.
- Phiên lỗi do rate limit (7/100) không được tính; nếu thử lại, token tăng nhẹ.
