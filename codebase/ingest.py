"""Trích chữ và tạo đoạn nguồn từ dữ liệu tải lên, hoàn toàn trong bộ nhớ."""

from io import BytesIO
from pathlib import PurePath
import re
from xml.etree import ElementTree
from zipfile import ZipFile


_EMPTY_ERROR = "không trích được chữ từ tài liệu"
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text(filename: str, data: bytes) -> str:
    """Trích TXT/MD, DOCX hoặc PDF từ bytes; không đọc hay ghi đường dẫn."""
    extension = PurePath(filename).suffix.lower()
    if extension not in {".txt", ".md", ".docx", ".pdf", ".pptx"}:
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
    elif extension == ".pptx":
        try:
            with ZipFile(BytesIO(data)) as archive:
                text = "\n\n".join("\n".join(parts) for _, parts in _pptx_slides(archive))
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
            "segment_id": "D%02d-S%s" % (buoi, ("%02d" if n < 100 else "%03d") % n),
            "session": "Buổi %d · %s" % (buoi, title),
            "source_title": "%s — đoạn %d" % (title, n),
            "updated_date": updated_date,
            "full_text": segment,
            "origin": "upload",
        }
        for n, segment in enumerate(split_segments(text), 1)
    ]


# ---------------------------------------------------------------- ảnh trong tài liệu

_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MIN_IMG_SIDE = 140          # bỏ biểu tượng / viền / logo nhỏ
MIN_IMG_AREA = 28000
MAX_IMG_SIDE = 1400


def _pptx_slides(archive):
    """[(số slide, [dòng chữ])] theo thứ tự slide trong file PPTX."""
    names = sorted((n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                   key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
    out = []
    for n in names:
        root = ElementTree.fromstring(archive.read(n))
        lines = []
        for para in root.iter(_A_NS + "p"):
            t = "".join(node.text or "" for node in para.iter(_A_NS + "t")).strip()
            if t:
                lines.append(t)
        out.append((int(re.search(r"(\d+)\.xml", n).group(1)), lines))
    return out


def _norm_image(raw: bytes):
    """Chuẩn hoá ảnh: bỏ ảnh quá nhỏ, thu nhỏ còn tối đa 1400px, PNG nếu có nền trong suốt, còn lại JPEG. (bytes, ext, w, h) hoặc None."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception:
        return None
    w, h = img.size
    if min(w, h) < MIN_IMG_SIDE or w * h < MIN_IMG_AREA or max(w, h) / max(1, min(w, h)) > 8:
        return None
    if max(w, h) > MAX_IMG_SIDE:
        img.thumbnail((MAX_IMG_SIDE, MAX_IMG_SIDE))
        w, h = img.size
    out = BytesIO()
    if img.mode in ("RGBA", "LA", "P") and ("A" in img.getbands() or "transparency" in img.info):
        img.convert("RGBA").save(out, "PNG", optimize=True)
        return out.getvalue(), "png", w, h
    img.convert("RGB").save(out, "JPEG", quality=86, optimize=True)
    return out.getvalue(), "jpg", w, h


def extract_images(filename: str, data: bytes) -> list[dict]:
    """Lấy ảnh nhúng trong PDF / DOCX / PPTX. Mỗi ảnh: {data, ext, w, h, anchor} — anchor là chữ ở cùng trang / gần ảnh,
    dùng để gắn ảnh vào đúng đoạn nguồn. Không đọc / ghi đĩa. Ảnh lỗi bị bỏ qua, không bao giờ raise."""
    extension = PurePath(filename).suffix.lower()
    raws = []       # (bytes, anchor)
    try:
        if extension == ".pdf":
            from pypdf import PdfReader
            for page in PdfReader(BytesIO(data)).pages:
                anchor = page.extract_text() or ""
                try:
                    imgs = list(page.images)
                except Exception:
                    imgs = []
                for im in imgs:
                    try:
                        raws.append((im.data, anchor))
                    except Exception:
                        continue
        elif extension == ".docx":
            with ZipFile(BytesIO(data)) as archive:
                rels = ElementTree.fromstring(archive.read("word/_rels/document.xml.rels"))
                target = {r.get("Id"): r.get("Target") for r in rels}
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                texts = []
                paras = list(root.iter(_WORD_NS + "p"))
                texts = ["".join(n.text or "" for n in p.iter(_WORD_NS + "t")).strip() for p in paras]
                for i, p in enumerate(paras):
                    for blip in p.iter(_A_NS + "blip"):
                        rid = blip.get(_R_NS + "embed")
                        path = target.get(rid or "")
                        if not path:
                            continue
                        path = path.lstrip("/")
                        path = path if path.startswith("word/") else "word/" + path
                        near = [t for t in texts[max(0, i - 2):i + 1] if t] or [t for t in texts[i + 1:i + 3] if t]
                        raws.append((archive.read(path), " ".join(near)))
        elif extension == ".pptx":
            with ZipFile(BytesIO(data)) as archive:
                for num, lines in _pptx_slides(archive):
                    relp = "ppt/slides/_rels/slide%d.xml.rels" % num
                    if relp not in archive.namelist():
                        continue
                    for r in ElementTree.fromstring(archive.read(relp)):
                        if r.get("Type", "").endswith("/image"):
                            path = r.get("Target", "").replace("../", "ppt/").lstrip("/")
                            if path in archive.namelist():
                                raws.append((archive.read(path), " ".join(lines)))
    except Exception:
        pass
    out, seen = [], set()
    for raw, anchor in raws:
        key = hash(raw)
        if key in seen:
            continue
        seen.add(key)
        norm = _norm_image(raw)
        if norm:
            out.append({"data": norm[0], "ext": norm[1], "w": norm[2], "h": norm[3], "anchor": anchor})
    return out


def _words(text):
    return set(w for w in re.findall(r"\w+", (text or "").lower()) if len(w) > 2)


def attach_images(segments: list[dict], images: list[dict]) -> list[tuple[dict, dict]]:
    """Gắn mỗi ảnh vào đoạn nguồn có nhiều từ trùng nhất với chữ quanh ảnh. Trả [(đoạn, ảnh)] theo thứ tự ảnh;
    ảnh không có chữ quanh được gắn cùng đoạn với ảnh trước (hoặc đoạn đầu)."""
    seg_words = [_words(s["full_text"]) for s in segments]
    pairs, last = [], 0
    for im in images:
        aw = _words(im.get("anchor", ""))
        best, best_score = None, 0.0
        if aw:
            for i, sw in enumerate(seg_words):
                if sw:
                    score = len(sw & aw) / len(sw)
                    if score > best_score:
                        best, best_score = i, score
        idx = best if best is not None else last
        last = idx
        pairs.append((segments[idx], im))
    return pairs
