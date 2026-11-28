# task_plan.md — kế hoạch và quyết định đã chốt

Phiên mới: đọc CLAUDE.md, AGENTS.md, file này và progress.md rồi làm tiếp. Giải thích hệ thống: docs/implementation.md.

## Quyết định đã chốt (không hỏi lại)
- Provider anthropic qua API_BASE_URL (trong .env). Sonnet 5.5 (claude-sonnet-5-5) để sinh, Haiku 5.5 (claude-haiku-5-5) để kiểm. call_model(system, user, model=None) trả đúng tên model đã gọi.
- Workflow cố định, không agent. Slide xuất HTML tự chứa. TTS: edge-tts. PDF quiz: fpdf2 (hoặc HTML nếu pip lỗi).
- FastAPI bọc answer() trong codebase/api.py. KHÔNG làm UI: nhóm sẽ đưa prototype.
- KHÔNG git add/commit/push. Chờ người dùng duyệt.
- Ngân sách key 20 USD: dừng và báo nếu lũy kế chạm 15 USD. Tối đa 3 vòng eval chính thức. Giá: Sonnet 5.5 2/10 USD, Haiku 5.5 0.10/0.50 USD mỗi 1M token (further-reading/model-prices.md).
- Không sửa: eval/benchmark.csv, eval/metric_spec.yaml, spec.md §7, run.py, tracing.py, run_eval.py, simulate.py.
- Giao Codex: codebase/exporters.py + tests/. Antigravity: chưa giao (chờ UI prototype).
- Cảnh báo cho nhóm: khảo sát n=7 < 20 → R1 tối đa 5 và không xét giải; cần phỏng vấn ≥3 hoặc khảo sát ≥20 người ngoài nhóm.

## Checkpoint (CP1, CP2 nhóm ĐÃ NỘP). Xong CP nào thì báo người dùng để họ nộp
- CP3 · 10:00 Thứ Bảy 28/11: bằng chứng pain đạt ngưỡng ≥1 nguồn + ≥5 trích dẫn nguyên văn (evidence/summary.md); bộ câu thử 20–30 câu (≥5 kho, ≥2 tu_choi) ✓ 25 câu; video 30 giây bản chạy thử gọi AI thật (NHÓM làm, ẩn danh/Drive); kết quả lượt 1 (x/N) + run ID ✓ run-1@20261127-233321 = 20/25; spec.md §0–§7 đủ (điền §7 kết quả); phần chưa xong.
- CP4 · 14:30 Thứ Bảy 28/11: link repo + phòng demo; tích 7 hạng mục (01-challenge-brief); kết quả lượt 1 → lượt 2; chi phí / task thành công ở kịch bản cơ sở + tên model (simulate); demo-slides.pdf ở thư mục gốc + link video demo dự phòng; phần chưa xong.
- Hạn 23:59 Thứ Bảy 28/11: changelog spec.md §10, reflection mỗi người, không sửa chuẩn đạt/câu thử/kết quả lượt cũ.

## Các bước
1. [x] ai.py nối model, requirements, cài thư viện, eval --try
2. [x] tools.py: search_sources, get_segment, submit_for_review
3. [x] agent.py: router, sinh quiz/slide, kiểm nhãn, từ chối
4. [x] eval lượt 1 + tự chấm cột pass + nhóm lỗi
5. [x] cải tiến + eval lượt 2 (đến run-4: 25/25)
6. [x] exporters.py (Codex) + nối vào luồng (chưa nối vào `answer()`; API gọi riêng)
7. [x] api.py: đã chạy thử dưới uvicorn (quiz + slide, 2 cổng); chưa kiểm /api/review riêng và chưa ghép UI
8. [x] simulate + điền cost/ (93/100 phiên hợp lệ)
9. [x] cập nhật docs/implementation.md mục 9
10. [x] UI `ui/` dựng theo prototype (Claude Code tự làm; Antigravity bị chặn quyền headless), đã chạy thử trên trình duyệt
11. [ ] chờ nhóm: phiếu khảo sát thêm, video, hypothesis.md, người chấm thứ hai, demo-slides.pdf
