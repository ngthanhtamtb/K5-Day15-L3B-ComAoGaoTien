"""Trích chữ và tạo đoạn nguồn từ dữ liệu tải lên, hoàn toàn trong bộ nhớ."""

from io import BytesIO
from pathlib import PurePath
import re
from xml.etree import ElementTree
from zipfile import ZipFile


MAX_BYTES = 5 * 1024 * 1024
MAX_SEGMENTS = 200
_EMPTY_ERROR = "không trích được chữ từ tài liệu"
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text(filename: str, data: bytes) -> str:
    """Trích TXT/MD, DOCX hoặc PDF từ bytes; không đọc hay ghi đường dẫn."""
    if len(data) > MAX_BYTES:
        raise ValueError("tài liệu quá lớn")
    extension = PurePath(filename).suffix.lower()
    if extension not in {".txt", ".md", ".docx", ".pdf"}:
        raise ValueError(f"định dạng không hỗ trợ: {extension}")
    if not data:
        raise ValueError(_EMPTY_ERROR)

    if extension in {".txt", ".md"}:
        for encoding in ("utf-8-sig", "cp1258", "latin-1"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    elif extension == ".docx":
        try:
            with ZipFile(BytesIO(data)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
            paragraphs = []
            for paragraph in root.iter(_WORD_NS + "p"):
                parts = []
                for node in paragraph.iter():
                    if node.tag == _WORD_NS + "t":
                        parts.append(node.text or "")
                    elif node.tag == _WORD_NS + "tab":
                        parts.append("\t")
                    elif node.tag in {_WORD_NS + "br", _WORD_NS + "cr"}:
                        parts.append(" ")
                paragraphs.append("".join(parts))
            text = "\n".join(paragraphs)
        except Exception as exc:
            raise ValueError(_EMPTY_ERROR) from exc
    else:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("cần cài thư viện pypdf để đọc PDF") from exc
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError(_EMPTY_ERROR) from exc

    text = text.strip()
    if not text:
        raise ValueError(_EMPTY_ERROR)
    return text


def _bounded_parts(text: str, max_chars: int):
    """Ưu tiên câu, rồi từ; chỉ cắt giữa từ nếu chính từ đó quá dài."""
    for sentence in re.split(r"(?<=[.?!])\s+", text):
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut <= 0:
                cut = max_chars
            yield sentence[:cut]
            sentence = sentence[cut:].lstrip()
        if sentence:
            yield sentence


def split_segments(text: str, max_chars: int = 900, min_chars: int = 200) -> list[str]:
    """Chuẩn hoá khoảng trắng và gộp đoạn ngắn trong giới hạn độ dài.

    Đoạn cuối hoặc đoạn ngay trước một đoạn đầy có thể ngắn hơn min_chars.
    """
    if (type(max_chars) is not int or type(min_chars) is not int
            or not 0 < min_chars <= max_chars):
        raise ValueError("độ dài đoạn phải là số nguyên và 0 < min_chars <= max_chars")
    segments = []
    pending = ""

    def append(segment):
        segments.append(segment)
        if len(segments) > MAX_SEGMENTS:
            raise ValueError("tài liệu vượt quá 200 đoạn")

    for line in text.splitlines():
        paragraph = " ".join(line.split())
        if not paragraph:
            continue
        parts = _bounded_parts(paragraph, max_chars) if len(paragraph) > max_chars else [paragraph]
        for part in parts:
            if pending and len(pending) + 1 + len(part) > max_chars:
                append(pending)
                pending = ""
            pending = f"{pending} {part}" if pending else part
            if len(pending) >= min_chars:
                append(pending)
                pending = ""
    if pending:
        append(pending)
    return segments


def build_segments(title: str, text: str, buoi: int, updated_date: str) -> list[dict]:
    """Tạo bản ghi nguồn tải lên; buổi 1–9 dành cho kho nguồn gốc."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError("tiêu đề không được rỗng")
    if type(buoi) is not int or not 10 <= buoi <= 99:
        raise ValueError("buổi phải là số nguyên trong khoảng 10 đến 99")
    title = title.strip()
    return [
        {
            "segment_id": "D%02d-S%02d" % (buoi, n),
            "session": "Buổi %d · %s" % (buoi, title),
            "source_title": "%s — đoạn %d" % (title, n),
            "updated_date": updated_date,
            "full_text": segment,
            "origin": "upload",
        }
        for n, segment in enumerate(split_segments(text), 1)
    ]
