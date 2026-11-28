# ScriptGuard web UI

Giao diện thuần HTML/CSS/JS dùng **ES module** của trình duyệt: không build, không framework, không npm.
Backend EduGuard (`backend/eduguard-backend/backend`) phục vụ thư mục này tại `/ui`, cùng origin với API.

```
cd backend/eduguard-backend/backend
.venv\Scripts\python -m uvicorn main:app --port 8077
# mở http://127.0.0.1:8077/ui/
```

API ở chỗ khác: `localStorage.setItem("eduguard.apiBase", "http://host:8077/api/v1/edu")`.
Bản UI cũ (gọi `codebase/api.py` của prototype hackathon) giữ nguyên ở `legacy/`, mở tại `/ui/legacy/` khi chạy `codebase/api.py`.

## Cấu trúc

```
index.html            khung trang, nạp css/* và js/main.js
css/
  tokens.css          màu (theo prototype) + dark mode
  base.css            reset, layout, thanh trên
  components.css      nút, form, badge, stepper, panel nguồn, toast, Agent verify
  screens.css         bố cục riêng từng màn (review split, slide studio, quiz…)
js/
  main.js             router + khung; thêm màn = 1 dòng trong ROUTES
  config.js           apiBase, chu kỳ poll job
  core/  dom.js       h() dựng DOM (chỉ text node, không innerHTML), icon, htmlToText
         router.js    hash router "#/scripts/:id"
         store.js     store dùng chung (trace, toast, gói) + prefs (localStorage, không bắt buộc)
         format.js    định dạng thời gian, số, chi phí
  api/   http.js      fetch + lỗi theo format backend
         edu.js       MỌI endpoint /api/v1/edu (màn hình không tự ghép URL)
  components/         ui.js (badge, nút, busy, stepper…), shell, agentPanel, sourcePanel,
                      audioTrack (track A1..An), slideCanvas (vẽ JSON PPTist chỉ đọc)
  screens/            library · document · scriptNew · scriptReview · slideStudio · quizNew · quizReview
```

## Màn hình ↔ endpoint

| Màn | Route | Endpoint chính |
|---|---|---|
| Thư viện | `#/` | `GET /documents` `/scripts` `/quizzes` · `POST /documents` (MD/TXT/DOCX) · `POST /documents/async` + `/jobs/{id}` (PDF/PPTX) |
| Tài liệu | `#/documents/:docId` | `GET /documents/{id}` — đoạn nguồn, hình, bảng |
| Tạo kịch bản | `#/scripts/new?doc=` | `POST /scripts` (dán `noiDung` hoặc sinh theo `chuDe`) |
| Rà soát (cổng 1) | `#/scripts/:id` | `/decisions` · `/accept-matching` · `/submit` |
| Slide & giọng (cổng 2) | `#/scripts/:id/slides` | `/slides` · `/voice/estimate` · `/voice` + `/jobs/{id}` · `/revise` · `GET /templates`, `/voice/voices` |
| Tạo quiz | `#/quizzes/new?doc=` | `POST /documents/{id}/quiz/generate` |
| Kiểm quiz | `#/quizzes/:id` | `/decision` · `PATCH` câu + `/verify` · `/evaluate` · `/fixes/*` · `/submit` · `/pdf?answers=` |

Mọi response có gọi model trả kèm `trace`; màn hình chuyển cho `setTrace()` để panel "Agent đã kiểm gì" hiển thị.

## Thêm một màn

1. Tạo `js/screens/<ten>.js` export `mount(el, { params, query })`, trả về hàm dọn dẹp nếu có listener toàn cục.
2. Thêm endpoint vào `js/api/edu.js` (nếu cần).
3. Thêm một dòng vào `ROUTES` trong `js/main.js` (màn được tải lười bằng `import()`).

## Quy tắc

- Không dùng `innerHTML` / `insertAdjacentHTML`: dữ liệu từ API luôn là text node (`h()`); HTML của slide qua `htmlToText()`.
- Không có nút / đường nào "xuất bản": trạng thái cuối luôn là chờ duyệt.
- Câu `TU_CHOI` không có nút chấp nhận; "chấp nhận hàng loạt" chỉ áp dụng câu Khớp nguồn.
- Chỉ hiển thị số API trả về (token, chi phí); thiếu giá thì ghi "chưa có giá", không tự tính.
