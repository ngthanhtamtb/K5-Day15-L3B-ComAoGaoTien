"""Kiểm thử nạp tài liệu ngoại tuyến, dữ liệu dựng hoàn toàn trong bộ nhớ."""

from io import BytesIO
import importlib.util
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from codebase.ingest import build_segments, extract_text, split_segments


def make_docx(xml):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return stream.getvalue()


def make_pdf():
    # Hai trang với font chuẩn, xref và offset thật; không cần trình xuất PDF.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for text in (b"First page", b"Second page"):
        content = b"BT /F1 12 Tf 20 200 Td (" + text + b") Tj ET"
        objects.append(b"<< /Length %d >>\nstream\n" % len(content)
                       + content + b"\nendstream")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(b"%d 0 obj\n" % n + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(b"xref\n0 8\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(b"%010d 00000 n \n" % offset)
    pdf.extend(b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref)
    return bytes(pdf)


class IngestTests(unittest.TestCase):
    def test_vietnamese_utf8_and_bom(self):
        text = "Tiếng Việt có dấu: học tập và ứng dụng."
        for extension in ("txt", "MD", "TXT"):
            for encoding in ("utf-8", "utf-8-sig"):
                with self.subTest(extension=extension, encoding=encoding):
                    self.assertEqual(extract_text("bài." + extension, text.encode(encoding)), text)

    def test_legacy_encodings(self):
        for text, encoding in (("Tiếng", "utf-8"), ("Xin chào", "cp1258"), ("\x81 café", "latin-1")):
            with self.subTest(encoding=encoding):
                self.assertEqual(extract_text("a.txt", text.encode(encoding)), text)

    def test_docx_paragraphs_runs_and_table(self):
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>Xin </w:t></w:r><w:r><w:t>chào Việt Nam</w:t></w:r></w:p>
          <w:p><w:r><w:t>Cột</w:t><w:tab/><w:t>hai</w:t><w:br/><w:t>tiếp</w:t></w:r></w:p>
          <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Trong bảng</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
          </w:body></w:document>'''
        data = make_docx(xml)
        with patch("builtins.open", side_effect=AssertionError("Không được đọc đĩa")):
            self.assertEqual(extract_text("a.docx", data), "Xin chào Việt Nam\nCột\thai tiếp\nTrong bảng")

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "Chưa cài pypdf")
    def test_pdf_two_pages(self):
        self.assertEqual(extract_text("a.pdf", make_pdf()), "First page\n\nSecond page")

    def test_missing_pdf_dependency(self):
        with patch.dict("sys.modules", {"pypdf": None}):
            with self.assertRaisesRegex(ValueError, "cần cài thư viện pypdf"):
                extract_text("a.pdf", make_pdf())

    def test_unsupported_extension(self):
        for name in ("a.exe", "a", "a.csv"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "định dạng không hỗ trợ:"):
                extract_text(name, b"text")

    def test_no_size_limit(self):
        big = 6 * 1024 * 1024
        self.assertEqual(len(extract_text("a.txt", b"x" * big)), big)

    def test_empty_and_invalid_documents(self):
        for filename, data in (("a.txt", b""), ("a.md", b" \n\t"),
                               ("a.txt", b"\xef\xbb\xbf"), ("a.docx", b"bad zip"),
                               ("a.docx", make_docx("<bad")),
                               ("a.docx", make_docx("<document/>")), ("a.pdf", b"")):
            with self.subTest(filename=filename, data=data[:20]):
                with self.assertRaisesRegex(ValueError, "^không trích được chữ từ tài liệu$"):
                    extract_text(filename, data)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "Chưa cài pypdf")
    def test_invalid_and_blank_pdf(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        stream = BytesIO()
        writer.write(stream)
        for data in (b"not a pdf", stream.getvalue()):
            with self.assertRaisesRegex(ValueError, "^không trích được chữ từ tài liệu$"):
                extract_text("a.pdf", data)

    def test_merge_short_paragraphs_and_normalize_spaces(self):
        self.assertEqual(split_segments("  Một  hai\n\n ba\t bốn\r\nnăm sáu  ", 30, 12),
                         ["Một hai ba bốn", "năm sáu"])
        self.assertEqual(split_segments(" \n\t"), [])

    def test_sentence_boundaries(self):
        text = "Một câu. Hai câu? Ba câu! Câu cuối."
        self.assertEqual(split_segments(text, 17, 8), ["Một câu.", "Hai câu?", "Ba câu! Câu cuối."])

    def test_long_sentence_and_long_word_preserve_content(self):
        for text in ("nội dung " * 40, "x" * 85):
            with self.subTest(text=text):
                parts = split_segments(text, 30, 15)
                self.assertTrue(all(0 < len(part) <= 30 for part in parts))
                self.assertEqual("".join("".join(parts).split()), "".join(text.split()))
        text = "nội dung " * 40
        self.assertEqual(" ".join(split_segments(text, 30, 15)), " ".join(text.split()))

    def test_no_segment_count_limit(self):
        self.assertEqual(len(split_segments("abc\n" * 500, 3, 3)), 500)
        ids = [x["segment_id"] for x in build_segments("T", ("x" * 300 + "\n") * 150, 10, "2026-01-01")]
        self.assertEqual((ids[0], ids[98], ids[99]), ("D10-S01", "D10-S99", "D10-S100"))

    def test_invalid_lengths(self):
        for maximum, minimum in ((0, 1), (3, 4), (3, 0), (3.5, 1), (True, 1)):
            with self.subTest(maximum=maximum, minimum=minimum), self.assertRaises(ValueError):
                split_segments("text", maximum, minimum)

    def test_build_exact_schema_and_ids(self):
        text = "Nội dung. " * 25
        segments = build_segments("Tài liệu", text + "\n" + text, 10, "2026-11-28")
        self.assertEqual(len(segments), 2)
        for n, segment in enumerate(segments, 1):
            self.assertEqual(segment, {
                "segment_id": f"D10-S{n:02d}", "session": "Buổi 10 · Tài liệu",
                "source_title": f"Tài liệu — đoạn {n}", "updated_date": "2026-11-28",
                "full_text": text.strip(), "origin": "upload",
            })
        self.assertEqual(build_segments("Tên", "chữ", 99, "ngày")[0]["segment_id"], "D99-S01")

    def test_invalid_title_and_session(self):
        for title in ("", " \n\t"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                build_segments(title, "text", 10, "date")
        for session in (9, 100, -1, 10.5, "10", True):
            with self.subTest(session=session), self.assertRaises(ValueError):
                build_segments("Tên", "text", session, "date")


if __name__ == "__main__":
    unittest.main()


class ImageTests(unittest.TestCase):
    def test_docx_image_extracted_and_attached(self):
        from PIL import Image
        from codebase.ingest import attach_images, extract_images
        png = BytesIO()
        Image.new("RGB", (400, 300), (10, 120, 200)).save(png, "PNG")
        ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
              'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
        doc = ('<w:document %s><w:body><w:p><w:r><w:t>Embedding vector cosine similarity</w:t></w:r></w:p>'
               '<w:p><w:r><a:blip r:embed="rId1"/></w:r></w:p></w:body></w:document>' % ns)
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="media/image1.png"/></Relationships>')
        stream = BytesIO()
        with ZipFile(stream, "w") as z:
            z.writestr("word/document.xml", doc)
            z.writestr("word/_rels/document.xml.rels", rels)
            z.writestr("word/media/image1.png", png.getvalue())
        images = extract_images("a.docx", stream.getvalue())
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["ext"], "jpg")
        segs = [{"full_text": "Kho dữ liệu khác hoàn toàn"}, {"full_text": "Embedding vector cosine similarity đo độ gần"}]
        self.assertIs(attach_images(segs, images)[0][0], segs[1])

    def test_tiny_and_broken_images_are_skipped(self):
        from codebase.ingest import extract_images
        self.assertEqual(extract_images("a.docx", b"not a zip"), [])
