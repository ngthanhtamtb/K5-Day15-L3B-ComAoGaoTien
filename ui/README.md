# ScriptGuard web UI

HTML/CSS/JS thuần dùng **ES module** của trình duyệt: không build, không framework, không npm.
Backend EduGuard (`backend/eduguard-backend/backend`) phục vụ thư mục này tại `/ui`, cùng origin với API.

```
cd backend/eduguard-backend/backend
.venv\Scripts\python -m uvicorn main:app --port 8077
# mở http://127.0.0.1:8077/ui/
```

API ở chỗ khác: `localStorage.setItem("eduguard.apiBase", "http://host:8077/api/v1/edu")`.
Bản UI của prototype hackathon (gọi `codebase/api.py`) giữ ở `legacy/`.

## Thiết kế

Nguồn: `design-system/scriptguard/MASTER.md` + override `pages/workspace.md` (sinh bằng skill ui-ux-pro-max).
Minimalism & Swiss · Plus Jakarta Sans · màu chính teal `#0F766E` chữ trắng · light + dark.

- **Lấy tài liệu làm trung tâm:** Tài liệu → Bài giảng (kịch bản + slide + giọng đọc) hoặc Quiz. Không có menu, chỉ breadcrumb.
- **Progressive disclosure:** mỗi màn chỉ mở phần cần làm ("Cần xem"). Câu đã ổn, câu đã loại, nội dung tài liệu,
  đoạn nguồn, tuỳ chọn nâng cao, tuỳ chỉnh giọng / mẫu đều gập trong `<details>`.
- **Một nút chính mỗi màn**, đổi theo trạng thái: "Kiểm lại N câu" → "Áp dụng N đề xuất sửa" → "Sang slide & giọng đọc";
  "Tạo / Cập nhật giọng đọc"; "Tải đề PDF".
- **Không có bước chờ duyệt:** mọi câu được dùng trừ câu giáo viên bỏ hoặc câu chứa chỉ dẫn chèn (tự loại).
  Câu khớp nguồn không cần bấm gì. Bỏ câu có "Hoàn tác".
- Trạng thái luôn là chấm màu + chữ (không chỉ dựa vào màu); nút tối thiểu 44px; skeleton thay cho spinner.

## Cấu trúc

```
index.html
css/      tokens.css (màu, font, khoảng cách, dark mode) · base.css · components.css · screens.css
js/
  main.js             router + khung; thêm màn = 1 dòng trong ROUTES
  config.js
  core/               dom.js (h(): chỉ text node, không innerHTML) · router.js · store.js (trace, toast + hoàn tác, prefs) · format.js
  api/                http.js · edu.js (MỌI endpoint /api/v1/edu)
  components/         ui.js (button, busy, disclosure, healthBar, tag, skeleton…) · shell.js · agentPanel.js
                      claimCard.js (thẻ "cần xem" + dòng gọn) · sourcePanel.js · audioTrack.js · slideCanvas.js
  screens/            home.js · document.js · lesson.js (+ lessonScript.js, lessonSlides.js) · quiz.js
```

## Màn hình

| Màn | Route | Mặc định hiện | Gập lại |
|---|---|---|---|
| Tài liệu | `#/` | danh sách tài liệu + bài giảng / quiz kèm số "cần xem" (lần đầu: vùng kéo thả) | — |
| Một tài liệu | `#/documents/:id` (`?create=lesson\|quiz`) | "Tạo bài giảng": AI đề xuất kịch bản → kiểm nguồn → hình/bảng → giọng → slide HTML, một job có tiến độ | chủ đề, tên; "dán kịch bản có sẵn"; nội dung đã đọc |
| Bài giảng · Kịch bản | `#/scripts/:id` | câu cần xem (lý do, đề xuất) + thanh tỉ lệ nhãn | đoạn nguồn, câu ổn, câu đã loại |
| Bài giảng · Slide | `#/scripts/:id/slides` | slide HTML thật (iframe sandbox) + nút tạo giọng / mở slide | giọng & tốc độ, lời đọc từng slide (sửa tại chỗ) |
| Quiz | `#/quizzes/:id` | câu cần xem kèm phương án, lý do, gợi ý | câu ổn, câu đã bỏ, giải thích, đoạn nguồn |

## Thêm một màn

1. Tạo `js/screens/<ten>.js` export `mount(el, { params, query, shell })`; gọi `shell.setCrumbs([...])`; trả về hàm dọn dẹp nếu cần.
2. Thêm endpoint vào `js/api/edu.js`.
3. Thêm một dòng vào `ROUTES` trong `js/main.js`.

## Quy tắc

- Không `innerHTML` / `insertAdjacentHTML`: dữ liệu API luôn là text node; HTML của slide qua `htmlToText()`.
- Không có nút "xuất bản" / "gửi duyệt".
- Chỉ hiện số API trả về (token, chi phí); chưa có giá thì ghi "chưa cấu hình giá".
