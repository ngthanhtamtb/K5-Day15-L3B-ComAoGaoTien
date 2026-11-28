# progress.md — nhật ký tiến độ (cập nhật sau mỗi bước)

| Thời điểm | Việc | Kết quả | Chi phí API lũy kế |
|---|---|---|---|
| 2026-11-27 | Tạo task_plan.md, progress.md | xong | 0 |
| 2026-11-27 | ai.py nối Anthropic qua API_BASE_URL, call_model(model=...); pip cài fastapi/uvicorn/edge-tts/fpdf2 | gọi Sonnet + Haiku OK, token thật | ~0 |
| 2026-11-27 | tools.py (search_sources từ khoá + IDF bỏ dấu, get_segment, submit_for_review luôn cho_duyet) | thử tay OK | ~0 |
| 2026-11-27 | agent.py workflow: triage (Haiku) → sinh (Sonnet) → kiểm (Haiku) / duyệt cổng 1-2; code xác minh mã đoạn | eval --try 3 câu OK; sửa: sinh chỉ dùng đoạn -S, không dùng -Q (B03 trích D04-Q01 sai) | ~0.05 USD (ước tính từ token) |
| 2026-11-27 | Codex: codebase/exporters.py + tests/test_exporters.py (đã review diff) | 8 test qua; PDF/HTML/mp3 thật chạy được | — |
| 2026-11-27 | Eval lượt 1 (run-1@20261127-233321), tự chấm cột pass | 20/25 (80%): thuong 6/8, kho 11/14, tu_choi 3/3. Trượt B05 B12 B13 B14 B15. Token 54795 vào / 54161 ra (~0.7 USD theo giá Sonnet/Haiku, ước tính) | ~0.7 |
| 2026-11-27 | Cải tiến cho lượt 2 (agent.py): lấy mã đoạn đầu tiên hợp lệ thay vì hạ nhầm; lọc khẳng định bịa; prompt: nói gọn ≠ sai, mã ghi sẵn sai mà nội dung có nguồn khác → KHOP + cảnh báo | đã sửa | — |
| 2026-11-27 | Eval run-2@20261127-234248 (sau cải tiến 1), tự chấm | 22/25 (88%): thuong 6/8, kho 13/14, tu_choi 3/3. B05 B12 B13 B14 B15 đã qua. Trượt: B02, B03 (lỗi kỹ thuật: Sonnet hết 4096 token cho suy nghĩ, không có text), B04 (trích D01-S01 ngoài tập mong đợi). Token 65460 vào / 72327 ra | ~1.6 |
| 2026-11-27 | Sửa lỗi: ai.py MAX_TOKENS 8192 + gọi lại gấp đôi khi stop_reason=max_tokens (cộng token mọi lần); tools.search_sources tính tiêu đề + min_ratio 0.4 cho bước sinh | đã sửa; run-2 không sửa tay, chạy lại thành run-3 | — |
| 2026-11-27 | Eval run-3@20261127-235723, tự chấm | 23/25 (92%): trượt B15 (4 khẳng định, có KHOP), B18 (nhãn sai chính tả KHOP_NGUAN) | ~2.2 |
| 2026-11-28 | Sửa: chuẩn hoá nhãn theo tiền tố; _collapse cho DUYET_QUIZ; INJECT_RE + yêu cầu 2 cờ cùng báo | đã sửa | — |
| 2026-11-28 | Eval run-4@20261128-001420, tự chấm | **25/25 (100%)** (thuong 8/8, kho 14/14, tu_choi 3/3). Lưu ý: lạc quan (lặp 4 lượt trên cùng bộ) | ~3.1 |
| 2026-11-28 | Khảo sát (Desktop/Khao-Sat.xlsx): 22 phiếu, 18 hợp lệ → evidence/survey/results.csv, questions.md, evidence/summary.md; mine_preclass.py (không câu nào sai ≥50%, không tính là nguồn) | **18/20: DƯỚI NGƯỠNG** | — |
| 2026-11-28 | Cập nhật spec.md (§0,§1,§2,§7,§10), DATA_CARD.md, eval/report.md, eval/README.md, cost/personas.yaml (100 phiên, 3 persona từ khảo sát, 3 mức giá) | xong | — |
| 2026-11-28 | Prototype UI (artifact claude.ai) không đọc được ("Loading…"); cần nhóm gửi HTML/code | chờ nhóm | — |
| 2026-11-28 | simulate --try 5 --rate-from eval/run-4.csv | xong, 0 lỗi; ~0.025 USD/phiên theo giá BTC | — |
| 2026-11-28 | simulate đủ 100 phiên | **ĐÃ DỪNG GIỮA CHỪNG (tôi kill tiến trình)**: bảng điều khiển nhà cung cấp cho thấy chi thật 17.41 USD / 502 request (0.0347 USD/request), key chỉ còn ~2.5 USD; 100 phiên cần ~22 USD. Không có file simulate-N nào được ghi. Chờ người dùng đổi key | thực tế ~17.4 (số của nhà cung cấp, cao hơn nhiều ước tính của tôi) |
| 2026-11-28 | simulate đủ 100 phiên chạy lại sau khi người dùng gia hạn key (01:26–~03:20) | Xong: `cost/simulate-1.csv`; 93/100 hợp lệ, 7 phiên lỗi HTTP 403 rate_limit (người dùng chấp nhận); $0,0219/phiên giá niêm yết; điền `cost/cost-estimate.md`, spec §8–§10, implementation.md §9, task_plan.md | key gia hạn thêm, tổng đã dùng chưa đối chiếu |
| LƯU Ý CHI PHÍ | Chi thật / request ≈ 6.5 lần so với tính theo bảng giá BTC (0.0347 vs ~0.005) — cần ghi rõ trong cost/cost-estimate.md: số nộp tính theo giá niêm yết BTC, chi thật qua proxy cao hơn | — | — |
| 2026-11-28 | Phiếu 20 bổ sung vai "Giảng viên" (GV hướng dẫn đồ án) trong Khao-Sat.xlsx → tính hợp lệ; tính lại mọi số khảo sát | **19/20: vẫn dưới ngưỡng (thiếu 1)**; personas.yaml / simulate-1 giữ n = 18 | — |
| 2026-11-28 | ThongKeKhaoSat.xlsx (23 dòng): thêm phiếu 23 (Trợ giảng cho giảng viên, kiểm 3–5 bài/tháng) vào results.csv; tính lại mọi số; | **20/20 hợp lệ / 23 phiếu, đạt ngưỡng** | — |
| CÒN LẠI CP3 (nhóm) | video 30s; hypothesis.md; người thứ hai chấm 5 output; (khảo sát đã đạt ngưỡng); demo-slides.pdf, video demo dự phòng (CP4) | — | — |
| 2026-11-28 | demo-slides.pdf (8 trang) + slides/demo-slides.html (bấm chuyển trang); đẩy lên main (96db4cb) | xong | — |
| 2026-11-28 | Thêm tính năng: nạp tài liệu thật (Codex viết `codebase/ingest.py` + `tests/test_ingest.py`, Claude review; Claude nối `tools.py` / `api.py` / `ui/app.js`), `ai.py` thử lại 403 rate limit, mẫu / tỉ lệ khung / ghi chú áp dụng khi dựng slide, nút Đạt / Cần sửa trong panel Agent verify, `eval/stability.py`, `tests/test_features.py`. Thử thật: nạp .txt → quiz / rà soát ra mã D10-S01 đúng; slide options áp dụng; UI nạp + xoá + panel Đạt chạy trên trình duyệt | 32 test offline qua; `run.py check` sạch | ~0.2 (thử tay) |
| 2026-11-28 | `eval/stability.py --runs 3` (25 câu × 3 lần) → `eval/stability-1.csv/.md` | nhãn ổn định 24/25 câu, nhãn + mã đoạn 19/25; B09 lệch nhãn một lần; chi ước tính ~3,3 USD thật | ~3.5 |
