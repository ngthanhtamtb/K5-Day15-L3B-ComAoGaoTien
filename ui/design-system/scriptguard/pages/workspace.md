# Override: app workspace (mọi màn của ScriptGuard)

Quy tắc ở đây ghi đè `MASTER.md` cho toàn bộ ứng dụng. MASTER được sinh cho trang giới thiệu sản phẩm
(pattern "Product Demo + Features", nút chính màu cam); ScriptGuard là công cụ làm việc nên dùng các điểm dưới.

## Giữ từ MASTER
- Phong cách Minimalism & Swiss: nhiều khoảng trắng, phân cấp chữ rõ, ít đổ bóng.
- Font Plus Jakarta Sans (có subset tiếng Việt).
- Thang khoảng cách `--space-*` (density 5) và chuyển động nhẹ 150–250ms, tôn trọng `prefers-reduced-motion`.

## Điều chỉnh
| Mục | MASTER | Workspace | Vì sao |
|---|---|---|---|
| Màu chính | `#0D9488` chữ đen, CTA cam `#EA580C` | `#0F766E` chữ trắng (≈5.5:1) | Nút chính trong app cần chữ trắng đủ tương phản; cam dành cho cảnh báo, không dùng cho CTA |
| Nền | `#F0FDFA` (ngả teal) | `#F8FAFA` trung tính | Đọc văn bản dài (kịch bản, đoạn nguồn) |
| Card hover | nhấc lên `translateY(-2px)` | không nhấc, chỉ đổi viền | Danh sách dày đặc, tránh nhảy layout |
| Pattern trang | landing (hero, video, CTA) | không áp dụng | Ứng dụng, không phải trang marketing |

## Nguyên tắc tương tác (từ guideline của skill)
- `primary-action`: mỗi màn đúng một nút chính; còn lại là nút phụ / liên kết.
- `progressive-disclosure`: mặc định chỉ hiện việc cần làm ("Cần xem"); câu đã khớp nguồn, nội dung tài liệu, tuỳ chọn nâng cao, đoạn nguồn và chi phí nằm trong phần mở rộng.
- `progressive-loading`: thao tác > 1 giây dùng skeleton hoặc thanh tiến độ, không spinner trơn.
- `empty-states`: luôn có thông điệp + một hành động.
- `undo-support`: câu bị bỏ có thể khôi phục.
- Không có bước "chờ duyệt": mọi câu đều được dùng trừ khi giáo viên bỏ, hoặc câu chứa chỉ dẫn chèn (tự loại).
