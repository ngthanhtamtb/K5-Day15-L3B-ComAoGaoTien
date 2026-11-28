"""Công cụ của bài toán A3 — NHÓM VIẾT.

Mỗi công cụ là một hàm Python có @tool. Docstring ghi 4 ý như spec.md §4:
    tên · input · output · có tác động ra ngoài không.
Khung tự ghi mỗi lần gọi công cụ vào trace.
Công cụ có tác động ra ngoài chỉ tạo bản nháp chờ người duyệt (status "cho_duyet"), không tự xuất bản.
Dữ liệu: data/sources/segments.json (mô tả ở data/DATA_CARD.md).
"""
import json
import math
import os
import re
import unicodedata
import uuid

from tracing import tool, TOOLS  # noqa: F401  (TOOLS: danh sách công cụ đã đăng ký)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEGMENTS_PATH = os.path.join(ROOT, "data", "sources", "segments.json")
# Tài liệu người dùng nạp (buổi ≥ 10) nằm riêng, KHÔNG commit (data/uploads/ trong .gitignore). Bộ câu thử
# `eval` luôn chạy trên kho gốc 14 đoạn: đặt A3_NO_UPLOADS=1 (run_eval không cần sửa) để bỏ qua tài liệu nạp.
UPLOADS_PATH = os.path.join(ROOT, "data", "uploads", "segments.json")
MAX_RESULTS = 5
SNIPPET_LEN = 220

_STOP = {"la", "va", "cua", "cac", "mot", "nhung", "cho", "voi", "trong", "khi", "thi", "duoc", "nay",
         "den", "tu", "co", "khong", "bang", "nhu", "the", "nao", "gi", "hay", "hoac", "ra", "vao",
         "len", "xuong", "se", "da", "dang", "de", "o", "ma", "neu", "vi", "nen", "cung", "rat"}

_cache = {}
DRAFTS = {}   # draft_id -> gói nháp (chỉ trong bộ nhớ, status luôn "cho_duyet")


def _fold(text):
    """Bỏ dấu tiếng Việt, hạ chữ thường — để so khớp từ khoá không phụ thuộc dấu."""
    text = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", _fold(text)) if t not in _STOP and (len(t) >= 2)]


def load_segments():
    """Đọc kho đoạn tài liệu (có cache). Trả list dict."""
    if "segments" not in _cache:
        with open(SEGMENTS_PATH, encoding="utf-8") as f:
            _cache["segments"] = json.load(f)
        if not os.environ.get("A3_NO_UPLOADS") and os.path.exists(UPLOADS_PATH):
            with open(UPLOADS_PATH, encoding="utf-8") as f:
                _cache["segments"] = _cache["segments"] + json.load(f)
        docs = [set(_tokens(s["full_text"] + " " + s["source_title"])) for s in _cache["segments"]]
        n = len(docs)
        df = {}
        for d in docs:
            for t in d:
                df[t] = df.get(t, 0) + 1
        _cache["docs"] = docs
        _cache["titles"] = [set(_tokens(s["source_title"])) for s in _cache["segments"]]
        _cache["idf"] = {t: math.log(1 + n / c) for t, c in df.items()}
    return _cache["segments"]


def _read_uploads():
    if os.path.exists(UPLOADS_PATH):
        with open(UPLOADS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _write_uploads(segs):
    os.makedirs(os.path.dirname(UPLOADS_PATH), exist_ok=True)
    if not segs:
        if os.path.exists(UPLOADS_PATH):
            os.remove(UPLOADS_PATH)
    else:
        with open(UPLOADS_PATH, "w", encoding="utf-8") as f:
            json.dump(segs, f, ensure_ascii=False, indent=1)
    _cache.clear()


def next_upload_buoi():
    """Số buổi trống tiếp theo cho tài liệu nạp (từ 10). Không phải công cụ AI."""
    used = {int(s["segment_id"][1:3]) for s in _read_uploads()}
    return next(n for n in range(10, 100) if n not in used)


def add_upload(segments):
    """Thêm các đoạn của một tài liệu nạp (cùng một buổi). Không phải công cụ AI — API gọi sau khi người dùng nạp file."""
    buoi = {s["segment_id"][1:3] for s in segments}
    if len(buoi) != 1 or int(buoi.copy().pop()) < 10:
        raise ValueError("tài liệu nạp phải cùng một buổi, số buổi từ 10")
    current = [s for s in _read_uploads() if s["segment_id"][1:3] not in buoi]
    _write_uploads(current + list(segments))


def remove_upload(buoi):
    """Xoá tài liệu nạp của một buổi. Trả số đoạn đã xoá (0 nếu không có)."""
    key = "%02d" % int(buoi)
    cur = _read_uploads()
    keep = [s for s in cur if s["segment_id"][1:3] != key]
    if len(keep) != len(cur):
        _write_uploads(keep)
    return len(cur) - len(keep)


def available_sessions():
    """Danh sách số buổi có trong kho, vd [1, 4, 7]. Không phải công cụ AI — dùng trong code."""
    out = set()
    for s in load_segments():
        m = re.match(r"D(\d+)-", s["segment_id"])
        if m:
            out.add(int(m.group(1)))
    return sorted(out)


@tool
def search_sources(query: str, buoi: int = None, min_ratio: float = 0.0) -> list:
    """search_sources · Input: chủ đề / câu cần kiểm (str), số buổi (int, tuỳ chọn), min_ratio (0–1, tuỳ chọn:
    bỏ đoạn có điểm thấp hơn min_ratio × điểm cao nhất) ·
    Output: tối đa 5 đoạn [{segment_id, source_title, snippet, updated_date}] xếp theo độ khớp từ khoá
    (từ khớp trong tiêu đề được tính thêm), rỗng nếu không khớp · Không tác động ra ngoài."""
    segs = load_segments()
    q = set(_tokens(query))
    idf = _cache["idf"]
    scored = []
    for seg, doc, title in zip(segs, _cache["docs"], _cache["titles"]):
        if buoi is not None and not seg["segment_id"].startswith("D%02d-" % int(buoi)):
            continue
        score = sum(idf.get(t, 0.0) for t in q & doc) + sum(idf.get(t, 0.0) for t in q & title)
        if score > 0:
            scored.append((score, seg))
    scored.sort(key=lambda x: -x[0])
    if scored and min_ratio > 0:
        scored = [x for x in scored if x[0] >= min_ratio * scored[0][0]]
    return [{"segment_id": s["segment_id"], "source_title": s["source_title"],
             "snippet": s["full_text"][:SNIPPET_LEN], "updated_date": s["updated_date"]}
            for _, s in scored[:MAX_RESULTS]]


@tool
def get_segment(segment_id: str) -> dict:
    """get_segment · Input: mã đoạn (str) · Output: {segment_id, full_text, source_title, updated_date};
    mã không tồn tại → raise KeyError · Không tác động ra ngoài."""
    for seg in load_segments():
        if seg["segment_id"] == segment_id:
            return {k: seg[k] for k in ("segment_id", "full_text", "source_title", "updated_date")}
    raise KeyError("không có đoạn nguồn: %s" % segment_id)


def segment_exists(segment_id):
    """Kiểm mã đoạn có trong kho (code xác minh, không qua AI)."""
    return any(s["segment_id"] == segment_id for s in load_segments())


@tool
def submit_for_review(package: dict) -> dict:
    """submit_for_review · Input: gói {quiz, slides, audio, nhan} (dict) ·
    Output: {draft_id, status: "cho_duyet"} · CÓ tác động: tạo bản nháp chờ giảng viên duyệt trong bộ nhớ;
    KHÔNG tự xuất bản, KHÔNG gửi cho học viên — status luôn là cho_duyet."""
    draft_id = "draft-" + uuid.uuid4().hex[:8]
    DRAFTS[draft_id] = {"package": package, "status": "cho_duyet"}
    return {"draft_id": draft_id, "status": "cho_duyet"}
