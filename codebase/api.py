"""Lớp API web (FastAPI) bọc luồng A3 — NHÓM VIẾT. Giao diện web của nhóm chỉ cần gọi các endpoint này.

Chạy:  python -m uvicorn api:app --app-dir codebase --port 8000
Biến môi trường tuỳ chọn: CORS_ORIGINS (danh sách origin, cách nhau bằng dấu phẩy; mặc định "*" khi phát triển).

Vòng đời một bản nháp (KHÔNG có endpoint xuất bản / gửi học viên — chỉ giảng viên tự xuất bản bên ngoài hệ thống):
    POST /api/drafts                     sinh quiz hoặc slide (đã tự kiểm)            stage = cong_1
    POST /api/drafts/{id}/gate1          giảng viên chấp nhận / từ chối / sửa từng mục  (mục sửa được kiểm lại)
    POST /api/drafts/{id}/build          dựng PDF quiz hoặc slide HTML + giọng đọc     stage = cong_2
    POST /api/drafts/{id}/gate2          giảng viên sửa trực tiếp → kiểm lại, SAI thì đề xuất câu sửa + nguồn;
                                         sửa 1 slide chỉ sinh lại audio của slide đó
    POST /api/drafts/{id}/submit         chốt bản nháp: status "cho_duyet"            stage = cho_duyet
    POST /api/review                     kiểm một đoạn nội dung bất kỳ (DUYET_KICH_BAN / DUYET_QUIZ / DUYET_CUOI)
"""
import os
import re
import sys
import threading
import uuid
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import agent
import exporters
import tools
import tracing
from tools import available_sessions

# Giá niêm yết BTC (USD / 1 triệu token), xem cost/personas.yaml. Chi thật qua proxy cao hơn (cost/cost-estimate.md §5).
# Câu chèn chỉ dẫn trong kịch bản: mẫu của agent + ghi chú gửi "cho hệ thống" + lệnh bỏ qua duyệt / xuất bản.
INJECT = re.compile(agent.INJECT_RE.pattern + r"|\[\s*(ghi\s*ch[úu]|l[ưu]u\s*[ýy]|ch[ỉi]\s*d[ẫa]n)[^\]]*(h[ệe]\s*th[ốo]ng|AI|model)[^\]]*\]"
                    r"|(b[ỏo]\s*qua|kh[ôo]ng\s*c[ầa]n)\s+(b[ướu]+[ớo]c\s+)?duy[ệe]t|xu[ấa]t\s*b[ảa]n\s*ngay|t[ựu]\s*(đ[ộo]ng\s*)?xu[ấa]t\s*b[ảa]n",
                    agent.INJECT_RE.flags)
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}
_TRACE_LOCK = threading.Lock()    # tracing.begin/end dùng một biến toàn cục → tuần tự hoá các lượt gọi model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT_DIR = os.path.join(ROOT, "drafts")

app = FastAPI(title="A3 — quiz và slide có kiểm duyệt nguồn")
app.add_middleware(CORSMiddleware,
                   allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
                   allow_methods=["*"], allow_headers=["*"])

DRAFTS = {}   # draft_id -> dict. Chỉ trong bộ nhớ. status luôn là "cho_duyet" — không bao giờ "đã xuất bản".


class CreateBody(BaseModel):
    kind: str                        # "quiz" | "slide"
    buoi: int
    chu_de: str = ""                 # bắt buộc khi không có script_id
    so_luong: int = 3
    script_id: Optional[str] = None  # dựng từ kịch bản đã rà soát (POST /api/scripts)
    options: Optional[dict] = None   # mẫu, tỉ lệ khung, ghi chú người nói… — chỉ lưu lại, CHƯA áp dụng khi dựng slide


class Decision(BaseModel):
    index: int                      # vị trí mục, từ 1
    action: str                     # "accept" | "reject" | "edit"
    item: Optional[dict] = None     # mục đã sửa (khi action = edit): cùng khoá như mục gốc
    note: Optional[str] = None      # ghi chú của giảng viên (vd "Cần sửa: …")


class DecisionsBody(BaseModel):
    decisions: list[Decision]


class ReviewBody(BaseModel):
    mode: str            # DUYET_KICH_BAN | DUYET_QUIZ | DUYET_CUOI
    noi_dung: str


def _get(draft_id):
    d = DRAFTS.get(draft_id)
    if not d:
        raise HTTPException(404, "không có bản nháp %s" % draft_id)
    return d


def _traced(label, fn, *args, **kwargs):
    """Chạy fn trong khung trace, trả (kết quả, trace). trace: số gọi model / công cụ, token, chi phí theo giá niêm yết, từng bước."""
    with _TRACE_LOCK:
        tracing.begin(label)
        try:
            res = fn(*args, **kwargs)
        finally:
            summary, events = tracing.end()
    cost = sum((e.get("tokens_in") or 0) * PRICES.get(e.get("model"), (0, 0))[0]
               + (e.get("tokens_out") or 0) * PRICES.get(e.get("model"), (0, 0))[1]
               for e in events if e["kind"] == "model") / 1e6
    steps = [{"loai": e["kind"], "ten": e.get("name") or e.get("text", ""), "model": e.get("model"),
              "tokens_in": e.get("tokens_in"), "tokens_out": e.get("tokens_out"),
              "latency_s": e.get("latency_s", e.get("t")), "loi": e.get("error")} for e in events]
    return res, dict(summary, nhan=label, chi_phi_usd_niem_yet=round(cost, 5), cac_buoc=steps)


def _recheck(kind, items, indexes, mode, traces=None):
    """Kiểm lại các mục vừa sửa bằng cùng bộ gắn nhãn. Trả {index: {nhan, chen_chi_dan}}."""
    out = {}
    for i in indexes:
        try:
            text = agent._item_text(kind, items[i - 1], i)
        except KeyError as exc:
            raise HTTPException(422, "mục %d thiếu khoá %s" % (i, exc))
        (claims, injected), trace = _traced("%s mục %d" % (mode, i), agent._review, mode, text)
        if traces is not None:
            traces.append(trace)
        out[i] = {"nhan": claims, "chen_chi_dan": injected}
    return out


def _public(d):
    return dict(d)


@app.get("/health")
def health():
    return {"ok": True, "buoi_co_trong_kho": available_sessions()}


@app.post("/api/drafts")
def create_draft(body: CreateBody):
    if body.kind not in ("quiz", "slide"):
        raise HTTPException(422, "kind phải là quiz hoặc slide")
    if body.script_id:
        sc = _get_script(body.script_id)
        if any(c["quyet_dinh"] == "chua_quyet" for c in sc["claims"]):
            raise HTTPException(409, "kịch bản còn câu chưa quyết định; rà soát xong rồi mới dựng")
        kept = [c for c in sc["claims"] if c["quyet_dinh"] in ("chap_nhan", "da_sua") and c["nhan"] != "TU_CHOI"]
        if not kept:
            raise HTTPException(409, "không còn câu nào được giữ lại để dựng")
        res, trace = _traced("tạo %s từ kịch bản" % body.kind, agent.create_from_script,
                             sc["buoi"], kept, body.so_luong, body.chu_de, body.kind)
        chu_de = body.chu_de or "kịch bản " + body.script_id
    else:
        if not body.chu_de.strip():
            raise HTTPException(422, "cần chu_de hoặc script_id")
        tag = "TAO_QUIZ" if body.kind == "quiz" else "TAO_SLIDE"
        unit = "câu" if body.kind == "quiz" else "slide"
        res, trace = _traced("tạo " + body.kind, agent.answer,
                             "[%s] buổi: %d · chủ đề: %s · số %s: %d" % (tag, body.buoi, body.chu_de, unit, body.so_luong))
        chu_de = body.chu_de
    data = res.get("data", {})
    if data.get("status") != "cho_duyet":
        return {"created": False, "status": data.get("status"), "message": res["output"], "trace": trace}
    draft_id = "draft-" + uuid.uuid4().hex[:8]
    DRAFTS[draft_id] = {
        "draft_id": draft_id, "kind": body.kind, "buoi": body.buoi, "chu_de": chu_de,
        "script_id": body.script_id, "options": body.options or {},
        "items": data["items"], "nhan": data["nhan"], "stage": "cong_1", "status": "cho_duyet",
        "files": {}, "message": res["output"], "traces": [trace],
    }
    return {"created": True, "draft": _public(DRAFTS[draft_id])}


@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str):
    return _public(_get(draft_id))


@app.post("/api/drafts/{draft_id}/gate1")
def gate1(draft_id: str, body: DecisionsBody):
    d = _get(draft_id)
    if d["stage"] != "cong_1":
        raise HTTPException(409, "bản nháp không ở cổng 1 (stage=%s)" % d["stage"])
    items, edited, rejected = list(d["items"]), [], set()
    for dec in body.decisions:
        if not 1 <= dec.index <= len(items):
            raise HTTPException(422, "index %d ngoài phạm vi" % dec.index)
        if dec.action == "reject":
            rejected.add(dec.index)
        elif dec.action == "edit":
            if not dec.item:
                raise HTTPException(422, "action edit cần item")
            items[dec.index - 1] = dict(items[dec.index - 1], **dec.item)   # khoá không gửi (vd segment_id) giữ như mục gốc
            edited.append(dec.index)
        elif dec.action != "accept":
            raise HTTPException(422, "action phải là accept / reject / edit")
    checks = _recheck(d["kind"], items, edited, "DUYET_QUIZ" if d["kind"] == "quiz" else "DUYET_KICH_BAN", d["traces"])
    d["items"] = [it for i, it in enumerate(items, 1) if i not in rejected]
    d["rejected"] = sorted(rejected)
    d["notes"] = {dec.index: dec.note for dec in body.decisions if dec.note}   # ghi chú "Cần sửa" của giảng viên
    d["gate1_checks"] = checks
    return {"draft": _public(d), "kiem_lai_muc_sua": checks}


@app.post("/api/drafts/{draft_id}/build")
def build(draft_id: str):
    d = _get(draft_id)
    if d["stage"] not in ("cong_1", "cong_2"):
        raise HTTPException(409, "không thể dựng ở stage=%s" % d["stage"])
    if not d["items"]:
        raise HTTPException(409, "không còn mục nào sau cổng 1")
    out = os.path.join(DRAFT_DIR, draft_id)
    try:
        if d["kind"] == "quiz":
            d["files"] = exporters.export_quiz_pdf(d["items"], out, "Quiz buổi %d — %s" % (d["buoi"], d["chu_de"]))
        else:
            audio, errors = {}, {}
            for i, it in enumerate(d["items"], 1):
                try:
                    audio[i] = exporters.synthesize_voice(i, it["loi_thuyet_trinh"], out)
                except RuntimeError as exc:      # TTS lỗi mạng: vẫn dựng slide, báo rõ slide nào thiếu audio
                    errors[i] = str(exc)
            html = exporters.render_slides(d["items"], out, "Slide buổi %d — %s" % (d["buoi"], d["chu_de"]), audio)
            d["files"] = dict({"slides_html": html}, **{"audio_%d" % i: p for i, p in audio.items()})
            d["audio_errors"] = errors
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    d["stage"] = "cong_2"
    return _public(d)


@app.post("/api/drafts/{draft_id}/gate2")
def gate2(draft_id: str, body: DecisionsBody):
    d = _get(draft_id)
    if d["stage"] != "cong_2":
        raise HTTPException(409, "bản nháp không ở cổng 2 (stage=%s)" % d["stage"])
    items, edited = list(d["items"]), []
    for dec in body.decisions:
        if dec.action != "edit" or not dec.item or not 1 <= dec.index <= len(items):
            raise HTTPException(422, "cổng 2 chỉ nhận action=edit kèm item, index hợp lệ")
        items[dec.index - 1] = dict(items[dec.index - 1], **dec.item)
        edited.append(dec.index)
    checks = _recheck(d["kind"], items, edited, "DUYET_CUOI", d["traces"])
    d["items"] = items
    d["gate2_checks"] = checks      # giảng viên vẫn có quyền giữ bản của mình; SAI_NGUON kèm de_xuat_sua để họ chọn
    out = os.path.join(DRAFT_DIR, draft_id)
    title = "%s buổi %d — %s" % ("Quiz" if d["kind"] == "quiz" else "Slide", d["buoi"], d["chu_de"])
    if d["kind"] == "slide":        # sửa 1 slide → chỉ sinh lại audio của slide đó
        for i in edited:
            try:
                d["files"]["audio_%d" % i] = exporters.synthesize_voice(i, items[i - 1]["loi_thuyet_trinh"], out)
            except RuntimeError as exc:
                d.setdefault("audio_errors", {})[i] = str(exc)
        audio = {int(k.split("_")[1]): v for k, v in d["files"].items() if k.startswith("audio_")}
        d["files"]["slides_html"] = exporters.render_slides(items, out, title, audio)
    else:
        d["files"] = exporters.export_quiz_pdf(items, out, title)
    return {"draft": _public(d), "kiem_lai_muc_sua": checks}


@app.post("/api/drafts/{draft_id}/submit")
def submit(draft_id: str):
    d = _get(draft_id)
    if d["stage"] != "cong_2":
        raise HTTPException(409, "phải qua cổng 2 trước khi nộp (stage=%s)" % d["stage"])
    res = tools.submit_for_review({"kind": d["kind"], "items": d["items"], "files": d["files"], "nhan": d["nhan"]})
    d["stage"], d["status"], d["review_id"] = "cho_duyet", res["status"], res["draft_id"]
    return _public(d)


@app.post("/api/review")
def review(body: ReviewBody):
    if body.mode not in ("DUYET_KICH_BAN", "DUYET_QUIZ", "DUYET_CUOI"):
        raise HTTPException(422, "mode không hợp lệ")
    res, trace = _traced("review " + body.mode, agent.answer, "[%s] %s" % (body.mode, body.noi_dung))
    return {"output": res["output"], "data": res.get("data", {}), "trace": trace}


# ------------------------------------------------------------ kho nguồn (màn "Nhập bản nháp")

@app.get("/api/kho")
def kho():
    """Các buổi có trong kho: số buổi, tên, ngày cập nhật mới nhất, mã đoạn."""
    by = {}
    for s in tools.load_segments():
        m = re.search(r"\d+", s["session"])
        by.setdefault(int(m.group()) if m else 0, []).append(s)
    out = []
    for buoi, segs in by.items():
        cur = [s for s in segs if "bản cũ" not in s["session"]] or segs      # đoạn bản cũ không tính vào ngày cập nhật
        out.append({"buoi": buoi, "ten": re.sub(r"\s*\(bản cũ\)", "", cur[0]["session"]), "so_doan": len(segs),
                    "cap_nhat": max(s["updated_date"] for s in cur), "co_ban_cu": len(cur) != len(segs),
                    "doan": [s["segment_id"] for s in segs]})
    return sorted(out, key=lambda x: x["buoi"])


@app.get("/api/segments/{segment_id}")
def segment(segment_id: str):
    """Đoạn nguồn đầy đủ (hiển thị "Đoạn nguồn trích dẫn"). Mã dạng D01-S02."""
    try:
        return tools.get_segment(segment_id)
    except KeyError:
        raise HTTPException(404, "không có đoạn %s" % segment_id)


# ------------------------------------------------------------ rà soát kịch bản (cổng 1 kịch bản)
# Vòng đời: POST /api/scripts → (decisions | accept-matching)* → submit → dùng script_id ở POST /api/drafts.
# Câu giảng viên đã quyết: chap_nhan | tu_choi_cau | da_sua ; chưa quyết: chua_quyet. Hệ thống không tự quyết thay.

SCRIPTS = {}


class ScriptBody(BaseModel):
    buoi: int
    noi_dung: str


class ScriptDecision(BaseModel):
    index: int                        # vị trí câu, từ 1
    action: str                       # "accept" | "reject" | "edit" | "reset"
    noi_dung: Optional[str] = None    # câu đã sửa (khi action = edit)


class ScriptDecisionsBody(BaseModel):
    decisions: list[ScriptDecision]


def _get_script(script_id):
    sc = SCRIPTS.get(script_id)
    if not sc:
        raise HTTPException(404, "không có kịch bản %s" % script_id)
    return sc


def _decorate(claim, index):
    """Thêm vị trí, nguồn đầy đủ, quyết định; câu chứa chỉ dẫn chèn bị gắn TU_CHOI (không bao giờ đưa vào slide)."""
    c = dict(claim, index=index, quyet_dinh="chua_quyet", nguon=None)
    if INJECT.search(c["noi_dung"]):
        c.update(nhan="TU_CHOI", segment_id="",
                 ly_do="Câu chứa chỉ dẫn chèn cho hệ thống; hệ thống không làm theo và không đưa câu này vào slide.")
    elif c["segment_id"] and tools.segment_exists(c["segment_id"]):
        c["nguon"] = tools.get_segment(c["segment_id"])
    return c


def _script_public(sc):
    counts = {}
    for c in sc["claims"]:
        counts[c["nhan"]] = counts.get(c["nhan"], 0) + 1
    decided = sum(1 for c in sc["claims"] if c["quyet_dinh"] != "chua_quyet")
    return dict(sc, tong_cau=len(sc["claims"]), da_quyet=decided, dem_nhan=counts)


@app.post("/api/scripts")
def create_script(body: ScriptBody):
    if body.buoi not in available_sessions():
        raise HTTPException(422, "kho chưa có buổi %d (đang có %s)" % (body.buoi, available_sessions()))
    if not body.noi_dung.strip():
        raise HTTPException(422, "noi_dung rỗng")
    # Tách câu chứa chỉ dẫn chèn ra trước: chúng KHÔNG đi vào bước rà soát (tránh làm hỏng cả kịch bản) và luôn bị gắn TU_CHOI.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\]])\s+|\n+", body.noi_dung) if s.strip()]
    injected_at = [(sum(1 for t in sentences[:i] if not INJECT.search(t)), s)
                   for i, s in enumerate(sentences) if INJECT.search(s)]
    clean = " ".join(s for s in sentences if not INJECT.search(s))
    if not clean.strip():
        raise HTTPException(422, "kịch bản chỉ gồm chỉ dẫn chèn, không có khẳng định nào để rà soát")
    res, trace = _traced("rà soát kịch bản", agent.answer, "[DUYET_KICH_BAN] " + clean)
    data = res.get("data", {})
    if data.get("status") != "da_kiem":
        return {"created": False, "status": data.get("status"), "message": res["output"], "trace": trace}
    claims = [dict(c) for c in data["nhan"]]
    for before, text in reversed(injected_at):      # chèn lại đúng chỗ cũ (xấp xỉ nếu model gộp / tách câu)
        claims.insert(min(before, len(claims)), {"noi_dung": text, "nhan": "TU_CHOI", "segment_id": "", "ly_do": "",
                                                 "de_xuat_sua": "", "canh_bao_ma": "", "nguon_cu": ""})
    script_id = "script-" + uuid.uuid4().hex[:8]
    SCRIPTS[script_id] = {
        "script_id": script_id, "buoi": body.buoi, "noi_dung": body.noi_dung, "stage": "ra_soat", "status": "nhap",
        "chen_chi_dan": bool(injected_at) or data.get("chen_chi_dan", False),
        "claims": [_decorate(c, i) for i, c in enumerate(claims, 1)], "traces": [trace], "message": res["output"],
    }
    return {"created": True, "script": _script_public(SCRIPTS[script_id])}


@app.get("/api/scripts/{script_id}")
def get_script(script_id: str):
    return _script_public(_get_script(script_id))


@app.post("/api/scripts/{script_id}/decisions")
def script_decisions(script_id: str, body: ScriptDecisionsBody):
    sc = _get_script(script_id)
    if sc["stage"] != "ra_soat":
        raise HTTPException(409, "kịch bản đã gửi chờ duyệt (stage=%s)" % sc["stage"])
    claims = sc["claims"]
    for dec in body.decisions:
        if not 1 <= dec.index <= len(claims):
            raise HTTPException(422, "index %d ngoài phạm vi" % dec.index)
        c = claims[dec.index - 1]
        if dec.action == "accept":
            if c["nhan"] == "TU_CHOI":
                raise HTTPException(422, "câu %d là chỉ dẫn chèn, không thể chấp nhận" % dec.index)
            c["quyet_dinh"] = "chap_nhan"
        elif dec.action == "reject":
            c["quyet_dinh"] = "tu_choi_cau"
        elif dec.action == "reset":
            c["quyet_dinh"] = "chua_quyet"
        elif dec.action == "edit":
            if not (dec.noi_dung or "").strip():
                raise HTTPException(422, "action edit cần noi_dung")
            (new, injected), trace = _traced("kiểm lại câu %d" % dec.index, agent._review, "DUYET_KICH_BAN", dec.noi_dung)
            sc["traces"].append(trace)
            if injected or INJECT.search(dec.noi_dung) or not new:
                raise HTTPException(422, "câu sửa không kiểm được hoặc chứa chỉ dẫn chèn")
            fresh = _decorate(new[0], dec.index)
            fresh["noi_dung"] = dec.noi_dung
            fresh["quyet_dinh"] = "da_sua"
            claims[dec.index - 1] = fresh
        else:
            raise HTTPException(422, "action phải là accept / reject / edit / reset")
    return _script_public(sc)


@app.post("/api/scripts/{script_id}/accept-matching")
def script_accept_matching(script_id: str):
    """Nút "Chấp nhận mọi câu Khớp nguồn chưa quyết": chỉ câu KHOP_NGUON và chưa quyết; SAI / THIEU / TU_CHOI giữ nguyên."""
    sc = _get_script(script_id)
    if sc["stage"] != "ra_soat":
        raise HTTPException(409, "kịch bản đã gửi chờ duyệt (stage=%s)" % sc["stage"])
    n = 0
    for c in sc["claims"]:
        if c["nhan"] == "KHOP_NGUON" and c["quyet_dinh"] == "chua_quyet":
            c["quyet_dinh"] = "chap_nhan"
            n += 1
    return dict(_script_public(sc), vua_chap_nhan=n)


@app.post("/api/scripts/{script_id}/submit")
def script_submit(script_id: str):
    sc = _get_script(script_id)
    left = sum(1 for c in sc["claims"] if c["quyet_dinh"] == "chua_quyet")
    if left:
        raise HTTPException(409, "còn %d câu chưa quyết định" % left)
    res = tools.submit_for_review({"kind": "script", "buoi": sc["buoi"], "claims": sc["claims"]})
    sc["stage"], sc["status"], sc["review_id"] = "da_ra_soat", res["status"], res["draft_id"]
    return _script_public(sc)


@app.get("/api/drafts/{draft_id}/files/{name}")
def download(draft_id: str, name: str):
    d = _get(draft_id)
    path = d["files"].get(name)
    if not path:    # cũng cho tải theo tên file thật (vd slide_1.mp3, vì HTML slide tham chiếu audio theo tên này)
        path = next((p for p in d["files"].values() if os.path.basename(p) == name), None)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "không có file %s" % name)
    root = os.path.realpath(os.path.join(DRAFT_DIR, draft_id))
    if not os.path.realpath(path).startswith(root):
        raise HTTPException(403, "ngoài thư mục bản nháp")
    return FileResponse(path)


# Giao diện tĩnh (thư mục ui/ ở gốc repo) phục vụ cùng origin với API: http://localhost:8000/ui/
UI_DIR = os.path.join(ROOT, "ui")
if os.path.isdir(UI_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")
