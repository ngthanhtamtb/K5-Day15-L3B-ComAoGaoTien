# Việc: codebase/ingest.py — nạp tài liệu thật thành đoạn nguồn

## Mục tiêu
Tạo module thuần Python (chỉ thư viện chuẩn + `pypdf` cho PDF) biến file tài liệu (PDF/DOCX/TXT/MD) thành danh sách đoạn nguồn cùng định dạng `data/sources/segments.json`.

## File được phép tạo/sửa (chỉ những file này)
- `codebase/ingest.py` (mới)
- `tests/test_ingest.py` (mới, unittest, giống kiểu `tests/test_exporters.py`)

## Hợp đồng
- `extract_text(filename: str, data: bytes) -> str`: theo đuôi file: `.txt`/`.md` (UTF-8, bỏ BOM, fallback cp1258/latin-1), `.docx` (zipfile + xml `word/document.xml`, mỗi `w:p` một dòng, KHÔNG dùng python-docx), `.pdf` (pypdf, nối các trang bằng dòng trống). Đuôi khác → `ValueError("định dạng không hỗ trợ: ...")`. Rỗng/không trích được chữ → `ValueError("không trích được chữ từ tài liệu")`. Giới hạn 5 MB (`ValueError("tài liệu quá lớn")`).
- `split_segments(text: str, max_chars: int = 900, min_chars: int = 200) -> list[str]`: tách theo đoạn (dòng trống / xuống dòng), gộp đoạn ngắn cho tới ≥ min_chars, đoạn dài hơn max_chars thì tách theo câu (dấu `.?!` + khoảng trắng). Chuẩn hoá khoảng trắng. Không mất chữ, không đoạn rỗng. Tối đa 200 đoạn (quá thì `ValueError`).
- `build_segments(title: str, text: str, buoi: int, updated_date: str) -> list[dict]`: mỗi dict có đúng các khoá: `segment_id` = `"D%02d-S%02d" % (buoi, n)` (n từ 1), `session` = `"Buổi %d · %s" % (buoi, title)`, `source_title` = `"%s — đoạn %d" % (title, n)`, `updated_date`, `full_text`, `origin` = `"upload"`. `title` rỗng → `ValueError`. `buoi` phải trong 10..99 (buổi 1–9 dành cho kho gốc) → `ValueError`.
- Mọi thông báo lỗi bằng tiếng Việt.

## Tiêu chí nghiệm thu
- `python -m unittest tests.test_ingest -v` từ thư mục gốc dự án: tất cả qua; test có TXT tiếng Việt có dấu, DOCX dựng tay bằng zipfile, PDF tối thiểu dựng tay (hoặc skip nếu không dựng được), lỗi định dạng, quá lớn, tách câu, gộp đoạn ngắn, id đúng định dạng.
- Không đọc/ghi file nào ngoài bộ nhớ (module không đụng đĩa). Không sửa file nào khác. Tuân thủ AGENTS.md.
