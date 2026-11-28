"""Lớp API web (FastAPI) bọc luồng A3 — NHÓM VIẾT. Giao diện web của nhóm chỉ cần gọi các endpoint này.

Chạy:  python -m uvicorn api:app --app-dir codebase --port 8000
Biến môi trường tuỳ chọn: CORS_ORIGINS (danh sách origin, cách nhau bằng dấu phẩy; mặc định "*" khi phát triển).

LUỒNG CHÍNH (không có bước duyệt): tải tài liệu lên → tạo slide → tạo quiz → tải về.
    POST /api/kho/upload                 nạp PDF / DOCX / PPTX / TXT: trích chữ + ẢNH, cắt đoạn nguồn
    POST /api/jobs/deck                  tạo slide (nội dung + ảnh tài liệu + giọng đọc + HTML/PPTX)  → job_id
    POST /api/jobs/quiz                  tạo quiz trắc nghiệm + 2 PDF (đề, đáp án)                     → job_id
    GET  /api/jobs/{job_id}              tiến trình từng bước thật; xong thì có draft_id
    GET  /api/drafts/{id}/files/{name}   tải file (slides_html, slides_pptx, bundle_zip, exam_pdf, answer_pdf, audio_N)
Các endpoint cũ bên dưới (cổng 1 / cổng 2 / submit) giữ lại cho tương thích, giao diện mới không dùng.

Vòng đời một bản nháp cũ (KHÔNG có endpoint xuất bản / gửi học viên — chỉ giảng viên tự xuất bản bên ngoài hệ thống):
    POST /api/drafts                     sinh quiz hoặc slide (đã tự kiểm)            stage = cong_1
    POST /api/drafts/{id}/gate1          giảng viên chấp nhận / từ chối / sửa từng mục  (mục sửa được kiểm lại)
    POST /api/drafts/{id}/build          dựng PDF quiz hoặc slide HTML + giọng đọc     stage = cong_2
    POST /api/drafts/{id}/gate2          giảng viên sửa trực tiếp → kiểm lại, SAI thì đề xuất câu sửa + nguồn;
                                         sửa 1 slide chỉ sinh lại audio của slide đó
    POST /api/drafts/{id}/submit         chốt bản nháp: status "cho_duyet"            stage = cho_duyet
    POST /api/review                     kiểm một đoạn nội dung bất kỳ (DUYET_KICH_BAN / DUYET_QUIZ / DUYET_CUOI)
"""
import base64
import datetime
import json
import os
import re
import sys
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import agent
import exporters
import ingest
import pptx_export
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
STATE_FILE = os.path.join(DRAFT_DIR, "_state.json")

app = FastAPI(title="A3 — quiz và slide có kiểm duyệt nguồn")
app.add_middleware(CORSMiddleware,
                   allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
                   allow_methods=["*"], allow_headers=["*"])

DRAFTS = {}   # draft_id -> dict. Lưu bền ra drafts/_state.json; status luôn là "cho_duyet" — không bao giờ "đã xuất bản".
_STATE_LOCK = threading.Lock()
_LIVE_STATUS = {"active": False, "op": "", "phase": "", "detail": "", "done": 0, "total": 0, "t0": 0.0}


def _set_live(active: bool, op: str = "", phase: str = "", detail: str = "", done: int = 0, total: int = 0):
    now = time.perf_counter()
    _LIVE_STATUS.update(
        active=active,
        op=op if active else "",
        phase=phase if active else "",
        detail=detail if active else "",
        done=done if active else 0,
        total=total if active else 0,
        t0=(_LIVE_STATUS["t0"] or now) if active else 0.0,
    )


def _save_state():
    with _STATE_LOCK:
        os.makedirs(DRAFT_DIR, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"drafts": DRAFTS, "scripts": SCRIPTS}, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)


def _load_state():
    if not os.path.isfile(STATE_FILE):
        return
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("drafts"), dict):
            DRAFTS.update(data["drafts"])
        if isinstance(data.get("scripts"), dict):
            SCRIPTS.update(data["scripts"])
    except Exception:
        pass


class CreateBody(BaseModel):
    kind: str                        # "quiz" | "slide"
    buoi: int
    chu_de: str = ""                 # bắt buộc khi không có script_id
    so_luong: int = 3
    script_id: Optional[str] = None  # dựng từ kịch bản đã rà soát (POST /api/scripts)
    options: Optional[dict] = None   # slide: mau, ty_le, ghi_chu — áp dụng khi dựng slide (exporters.render_slides)


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


class VoiceBody(BaseModel):
    slide_index: Optional[int] = None        # None = tạo cho mọi slide; 1..N = chỉ slide đó
    voice: Optional[str] = None              # vi-VN-HoaiMyNeural | vi-VN-NamMinhNeural
    rate: Optional[str] = None               # -15% | +0% | +15% | +25%
    loi_thuyet_trinh: Optional[str] = None   # cập nhật lời thuyết trình riêng của slide_index
    recheck: bool = False                    # kiểm lại từng câu trong lời thuyết trình với kho nguồn


def _voice_opts(d: dict) -> tuple[str, str]:
    opts = d.get("options") or {}
    voice = opts.get("voice") if opts.get("voice") in exporters.ALLOWED_VOICES else "vi-VN-HoaiMyNeural"
    rate = opts.get("rate") if opts.get("rate") in exporters.ALLOWED_RATES else "+0%"
    return voice, rate


def _split_voice_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+|\n+", (text or "").strip()) if p.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


def _build_voice_meta(slide: dict, claims: list[dict] = None) -> list[dict]:
    """Tách lời thuyết trình thành các đoạn A1, A2… kèm ước lượng mốc thời gian, liên kết ý trên slide và nhãn kiểm."""
    sents = _split_voice_sentences(slide.get("loi_thuyet_trinh", ""))
    if not sents:
        return []
    bullets = [set(tools._tokens(b)) for b in (slide.get("y_chinh") or [])]
    weights = [max(8, len(s)) for s in sents]
    total_w = sum(weights) or 1
    est_dur = max(6, round(sum(len(s.split()) for s in sents) / 2.6))
    t_cur = 0.0
    out = []
    for idx, (sent, w) in enumerate(zip(sents, weights), 1):
        dur_i = est_dur * (w / total_w)
        t0, t1 = round(t_cur, 1), round(t_cur + dur_i, 1)
        t_cur += dur_i
        stoks = set(tools._tokens(sent))
        best_b, best_ov = None, 0
        for bi, btoks in enumerate(bullets, 1):
            ov = len(stoks & btoks)
            if ov > best_ov and ov >= 2:
                best_b, best_ov = bi, ov
        matched = None
        if claims:
            if len(claims) == len(sents):
                matched = claims[idx - 1]
            else:
                for c in claims:
                    ct = set(tools._tokens(c.get("noi_dung", "")))
                    if ct and len(ct & stoks) / max(1, len(ct)) >= 0.45:
                        matched = c
                        break
        nhan = (matched or {}).get("nhan") or "KHOP_NGUON"
        seg_id = (matched or {}).get("segment_id") or (slide.get("segment_id", "") if nhan != "THIEU_NGUON" else "")
        has_term = bool(re.search(r"\b(autoregressive|temperature|softmax|logits?|subword|context window|hallucination|few-shot|chain-of-thought|fine-tuning|embedding|cosine|chunk\w*|top-k|prompt)\b", sent, re.I))
        kind = "Ý %d trên slide" % best_b if best_b else ("Mở đầu / chuyển ý" if idx == 1 and len(sents) > 1 else "Ngoài slide")
        if has_term and nhan == "KHOP_NGUON":
            kind += " · có thuật ngữ Anh"
        out.append({
            "id": "A%d" % idx, "t0": t0, "t1": max(t0 + 1.0, t1), "est_dur": est_dur,
            "bullet": best_b, "kind": kind, "noi_dung": sent, "nhan": nhan,
            "segment_id": seg_id,
            "ly_do": (matched or {}).get("ly_do") or ("Khớp ý %d trên slide và đoạn nguồn %s." % (best_b, seg_id) if best_b and seg_id else "Lời dẫn thuyết trình khớp ngữ cảnh slide."),
            "de_xuat_sua": (matched or {}).get("de_xuat_sua") or "",
        })
    return out


def _get(draft_id):
    d = DRAFTS.get(draft_id)
    if not d:
        raise HTTPException(404, "không có bản nháp %s" % draft_id)
    return d


def _traced(label, fn, *args, **kwargs):
    """Chạy fn trong khung trace, trả (kết quả, trace). trace: số gọi model / công cụ, token, chi phí theo giá niêm yết, từng bước."""
    with _TRACE_LOCK:
        _LIVE_STATUS.update(active=True, phase=label, t0=_LIVE_STATUS["t0"] or time.perf_counter())
        tracing.begin(label)
        try:
            res = fn(*args, **kwargs)
        finally:
            summary, events = tracing.end()
            if not _LIVE_STATUS.get("op"):
                _set_live(False)
    cost = sum((e.get("tokens_in") or 0) * PRICES.get(e.get("model"), (0, 0))[0]
               + (e.get("tokens_out") or 0) * PRICES.get(e.get("model"), (0, 0))[1]
               for e in events if e["kind"] == "model") / 1e6
    steps = [{"loai": e["kind"], "ten": e.get("name") or e.get("text", ""), "model": e.get("model"),
              "tokens_in": e.get("tokens_in"), "tokens_out": e.get("tokens_out"),
              "latency_s": e.get("latency_s", e.get("t")), "loi": e.get("error")} for e in events]
    return res, dict(summary, nhan=label, chi_phi_usd_niem_yet=round(cost, 5), cac_buoc=steps)


@app.get("/api/progress")
def live_progress():
    """Trả tiến trình thực tế đang chạy trên server (đọc trực tiếp từ _LIVE_STATUS và sự kiện thật trong tracing._case)."""
    evs = list(tracing._case.get("events") or [])
    tools_ev = [e for e in evs if e.get("kind") == "tool"]
    models_ev = [e for e in evs if e.get("kind") == "model"]
    notes_ev = [e for e in evs if e.get("kind") == "note"]
    t0 = _LIVE_STATUS.get("t0") or tracing._case.get("t0") or 0.0
    active = bool(_LIVE_STATUS.get("active") or tracing._case.get("id"))
    return {
        "active": active,
        "op": _LIVE_STATUS.get("op") or "",
        "phase": _LIVE_STATUS.get("phase") or tracing._case.get("id") or "",
        "detail": _LIVE_STATUS.get("detail") or (notes_ev[-1].get("text", "") if notes_ev else ""),
        "done": _LIVE_STATUS.get("done") or 0,
        "total": _LIVE_STATUS.get("total") or 0,
        "elapsed_s": round(max(0.0, time.perf_counter() - t0), 1) if (active and t0) else 0.0,
        "tool_calls": len(tools_ev),
        "model_calls": len(models_ev),
        "tokens_in": sum(e.get("tokens_in") or 0 for e in models_ev),
        "tokens_out": sum(e.get("tokens_out") or 0 for e in models_ev),
        "last_tool": tools_ev[-1].get("name", "") if tools_ev else "",
        "last_model": models_ev[-1].get("model", "") if models_ev else "",
        "recent_steps": [
            {"loai": e.get("kind"), "ten": e.get("name") or e.get("text", ""), "model": e.get("model") or "", "t": e.get("t", 0)}
            for e in evs[-6:]
        ],
    }


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
    opts = dict(body.options or {})
    if body.kind == "slide":
        opts.setdefault("voice", "vi-VN-HoaiMyNeural")
        opts.setdefault("rate", "+0%")
    voice_segs = {str(i): _build_voice_meta(it) for i, it in enumerate(data["items"], 1)} if body.kind == "slide" else {}
    DRAFTS[draft_id] = {
        "draft_id": draft_id, "kind": body.kind, "buoi": body.buoi, "chu_de": chu_de,
        "script_id": body.script_id, "options": opts,
        "items": data["items"], "nhan": data["nhan"], "stage": "cong_1", "status": "cho_duyet",
        "files": {}, "audio_ts": {}, "voice_segments": voice_segs, "message": res["output"], "traces": [trace],
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save_state()
    return {"created": True, "draft": _public(DRAFTS[draft_id])}


@app.get("/api/drafts")
def list_drafts():
    items = []
    for d in reversed(list(DRAFTS.values())):
        items.append({
            "draft_id": d["draft_id"], "kind": d["kind"], "buoi": d["buoi"], "chu_de": d["chu_de"],
            "stage": d["stage"], "status": d["status"], "so_muc": len(d.get("items") or []),
            "has_html": "slides_html" in (d.get("files") or {}),
            "has_pdf": "exam_pdf" in (d.get("files") or {}),
            "created_at": d.get("created_at", ""),
        })
    return items


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
    if d["kind"] == "slide":
        kept_indices = [i for i in range(1, len(items) + 1) if i not in rejected]
        old_files = d.get("files") or {}
        old_ts = d.get("audio_ts") or {}
        new_files, new_ts, new_vsegs = {}, {}, {}
        for new_i, old_i in enumerate(kept_indices, 1):
            c_list = (checks.get(old_i) or {}).get("nhan")
            new_vsegs[str(new_i)] = _build_voice_meta(d["items"][new_i - 1], c_list)
            if old_i not in edited and ("audio_%d" % old_i) in old_files and os.path.isfile(old_files["audio_%d" % old_i]):
                new_files["audio_%d" % new_i] = old_files["audio_%d" % old_i]
                if str(old_i) in old_ts:
                    new_ts[str(new_i)] = old_ts[str(old_i)]
        d["files"] = new_files
        d["audio_ts"] = new_ts
        d["voice_segments"] = new_vsegs
    d["rejected"] = sorted(rejected)
    d["notes"] = {dec.index: dec.note for dec in body.decisions if dec.note}   # ghi chú "Cần sửa" của giảng viên
    d["gate1_checks"] = checks
    _save_state()
    return {"draft": _public(d), "kiem_lai_muc_sua": checks}


@app.post("/api/drafts/{draft_id}/build")
def build(draft_id: str):
    d = _get(draft_id)
    if d["stage"] not in ("cong_1", "cong_2"):
        raise HTTPException(409, "không thể dựng ở stage=%s" % d["stage"])
    if not d["items"]:
        raise HTTPException(409, "không còn mục nào sau cổng 1")
    out = os.path.join(DRAFT_DIR, draft_id)
    total_items = len(d["items"])
    _set_live(True, op="build", phase="Đang dựng bản hoàn chỉnh", detail="Chuẩn bị dựng %d mục" % total_items, done=0, total=total_items + 2)
    try:
        if d["kind"] == "quiz":
            _set_live(True, op="build", phase="Đang xuất 2 file PDF đề & đáp án", detail="Kết xuất Unicode PDF", done=1, total=2)
            d["files"] = exporters.export_quiz_pdf(d["items"], out, "Quiz buổi %d — %s" % (d["buoi"], d["chu_de"]))
        else:
            try:
                _set_live(True, op="build", phase="Thiết kế bố cục & vẽ sơ đồ SVG minh hoạ", detail="Sonnet 5.5 chọn layout & vẽ SVG cho %d slide" % total_items, done=0, total=total_items + 2)
                vis_res, vis_trace = _traced("thiết kế bố cục & sơ đồ slide", agent.design_slides_visuals, d["items"])
                if isinstance(vis_res, dict) and vis_res.get("items"):
                    d["items"] = vis_res["items"]
                d["traces"].append(vis_trace)
            except Exception:
                pass    # lỗi mạng khi vẽ visual: fallback về sơ đồ SVG mặc định, vẫn dựng slide
            voice, rate = _voice_opts(d)
            audio, errors = {}, {}
            ts_map = dict(d.get("audio_ts") or {})
            existing = d.get("files") or {}
            for i, it in enumerate(d["items"], 1):
                _set_live(True, op="build", phase="Tổng hợp giọng đọc thuyết trình", detail="Slide %d/%d: %s" % (i, total_items, it.get("tieu_de", "")), done=i, total=total_items + 2)
                cur_audio = existing.get("audio_%d" % i)
                if cur_audio and os.path.isfile(cur_audio) and d.get("_voice_used") == (voice, rate):
                    audio[i] = cur_audio
                    continue
                try:
                    audio[i] = exporters.synthesize_voice(i, it["loi_thuyet_trinh"], out, voice=voice, rate=rate)
                    ts_map[str(i)] = int(time.time() * 1000)
                except RuntimeError as exc:      # TTS lỗi mạng: vẫn dựng slide, báo rõ slide nào thiếu audio
                    errors[i] = str(exc)
            _set_live(True, op="build", phase="Kết xuất bản trình chiếu HTML", detail="Đóng gói giao diện slide & audio", done=total_items + 1, total=total_items + 2)
            html = exporters.render_slides(d["items"], out, "Slide buổi %d — %s" % (d["buoi"], d["chu_de"]), audio, d["options"])
            d["files"] = dict({"slides_html": html}, **{"audio_%d" % i: p for i, p in audio.items()})
            d["audio_ts"] = ts_map
            d["_voice_used"] = (voice, rate)
            d.setdefault("voice_segments", {str(i): _build_voice_meta(it) for i, it in enumerate(d["items"], 1)})
            d["audio_errors"] = errors
    except RuntimeError as exc:
        _set_live(False)
        raise HTTPException(500, str(exc))
    _set_live(False)
    d["stage"] = "cong_2"
    _save_state()
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
        voice, rate = _voice_opts(d)
        ts_map = d.setdefault("audio_ts", {})
        vsegs = d.setdefault("voice_segments", {})
        for i in edited:
            vsegs[str(i)] = _build_voice_meta(items[i - 1], (checks.get(i) or {}).get("nhan"))
            try:
                d["files"]["audio_%d" % i] = exporters.synthesize_voice(i, items[i - 1]["loi_thuyet_trinh"], out, voice=voice, rate=rate)
                ts_map[str(i)] = int(time.time() * 1000)
                d.get("audio_errors", {}).pop(i, None)
                d.get("audio_errors", {}).pop(str(i), None)
            except RuntimeError as exc:
                d.setdefault("audio_errors", {})[i] = str(exc)
        audio = {int(k.split("_")[1]): v for k, v in d["files"].items() if k.startswith("audio_")}
        d["files"]["slides_html"] = exporters.render_slides(items, out, title, audio, d["options"])
        d["_voice_used"] = (voice, rate)
    else:
        d["files"] = exporters.export_quiz_pdf(items, out, title)
    _save_state()
    return {"draft": _public(d), "kiem_lai_muc_sua": checks}


@app.post("/api/drafts/{draft_id}/voice")
def synthesize_draft_voice(draft_id: str, body: VoiceBody):
    """Tạo / tạo lại giọng đọc thuyết trình (TTS) cho 1 slide hoặc toàn bộ bộ slide ngay ở Cổng 1 hoặc Cổng 2;
    hỗ trợ đổi giọng (Hoài My / Nam Minh), tốc độ đọc, sửa lời thuyết trình và đối chiếu lại từng câu với nguồn."""
    d = _get(draft_id)
    if d["kind"] != "slide":
        raise HTTPException(422, "chỉ bản nháp slide mới có giọng thuyết trình")
    if d["stage"] == "cho_duyet":
        raise HTTPException(409, "bản nháp đã gửi chờ duyệt, không sửa giọng đọc")
    items = d["items"]
    if not items:
        raise HTTPException(409, "bản nháp không có slide nào")
    opts = d.setdefault("options", {})
    if body.voice is not None:
        if body.voice not in exporters.ALLOWED_VOICES:
            raise HTTPException(422, "giọng đọc không hợp lệ (chỉ hỗ trợ vi-VN-HoaiMyNeural và vi-VN-NamMinhNeural)")
        opts["voice"] = body.voice
    if body.rate is not None:
        if body.rate not in exporters.ALLOWED_RATES:
            raise HTTPException(422, "tốc độ đọc không hợp lệ")
        opts["rate"] = body.rate
    voice, rate = _voice_opts(d)

    if body.slide_index is not None:
        if not 1 <= body.slide_index <= len(items):
            raise HTTPException(422, "slide_index %d ngoài phạm vi 1..%d" % (body.slide_index, len(items)))
        targets = [body.slide_index]
    else:
        targets = list(range(1, len(items) + 1))

    vsegs = d.setdefault("voice_segments", {})
    voice_check = None
    if body.slide_index is not None and body.loi_thuyet_trinh is not None:
        new_text = body.loi_thuyet_trinh.strip()
        if not new_text:
            raise HTTPException(422, "lời thuyết trình không được rỗng")
        if INJECT.search(new_text):
            raise HTTPException(422, "lời thuyết trình chứa chỉ dẫn chèn cho hệ thống")
        items[body.slide_index - 1] = dict(items[body.slide_index - 1], loi_thuyet_trinh=new_text)
        d["items"] = items
        if body.recheck:
            mode = "DUYET_CUOI" if d["stage"] == "cong_2" else "DUYET_KICH_BAN"
            (claims, injected), trace = _traced("kiểm giọng đọc slide %d" % body.slide_index, agent._review, mode, new_text)
            d.setdefault("traces", []).append(trace)
            voice_check = {"nhan": claims, "chen_chi_dan": injected}
            d.setdefault("voice_checks", {})[str(body.slide_index)] = voice_check
            vsegs[str(body.slide_index)] = _build_voice_meta(items[body.slide_index - 1], claims)
        else:
            vsegs[str(body.slide_index)] = _build_voice_meta(items[body.slide_index - 1])

    out = os.path.join(DRAFT_DIR, draft_id)
    files = d.setdefault("files", {})
    ts_map = d.setdefault("audio_ts", {})
    errors = d.setdefault("audio_errors", {})
    for i in targets:
        if str(i) not in vsegs:
            vsegs[str(i)] = _build_voice_meta(items[i - 1])
        try:
            files["audio_%d" % i] = exporters.synthesize_voice(i, items[i - 1]["loi_thuyet_trinh"], out, voice=voice, rate=rate)
            ts_map[str(i)] = int(time.time() * 1000)
            errors.pop(i, None)
            errors.pop(str(i), None)
        except RuntimeError as exc:
            errors[str(i)] = str(exc)

    d["_voice_used"] = (voice, rate)
    if "slides_html" in files:
        _rebuild_deck_files(d)
    _save_state()
    return {"draft": _public(d), "kiem_lai_giong_doc": voice_check}


@app.post("/api/drafts/{draft_id}/submit")
def submit(draft_id: str):
    d = _get(draft_id)
    if d["stage"] != "cong_2":
        raise HTTPException(409, "phải qua cổng 2 trước khi nộp (stage=%s)" % d["stage"])
    res = tools.submit_for_review({"kind": d["kind"], "items": d["items"], "files": d["files"], "nhan": d["nhan"]})
    d["stage"], d["status"], d["review_id"] = "cho_duyet", res["status"], res["draft_id"]
    _save_state()
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
                    "doan": [s["segment_id"] for s in segs], "tai_len": buoi >= 10,
                    "anh": [n for s in segs for n in (s.get("images") or [])],
                    "so_ky_tu": sum(len(s["full_text"]) for s in segs),
                    "xem_truoc": cur[0]["full_text"][:260]})
    return sorted(out, key=lambda x: x["buoi"])


class UploadBody(BaseModel):
    filename: str                    # .pdf / .docx / .txt / .md
    content_b64: str                 # nội dung file, base64 (không dùng multipart để khỏi thêm phụ thuộc)
    title: str = ""                  # mặc định: tên file bỏ đuôi
    buoi: Optional[int] = None       # mặc định: số buổi trống tiếp theo (từ 10)


@app.post("/api/kho/upload")
def kho_upload(body: UploadBody):
    """Nạp tài liệu thật: trích chữ → cắt đoạn có segment_id (D10-S01…) → vào kho. Chỉ lưu cục bộ, không gọi model."""
    try:
        raw = base64.b64decode(body.content_b64, validate=True)
    except ValueError:
        raise HTTPException(422, "content_b64 không phải base64 hợp lệ")
    title = body.title.strip() or os.path.splitext(os.path.basename(body.filename))[0]
    try:
        text = ingest.extract_text(body.filename, raw)
        buoi = body.buoi if body.buoi is not None else tools.next_upload_buoi()
        segs = ingest.build_segments(title, text, buoi, datetime.date.today().isoformat())
        images = ingest.extract_images(body.filename, raw)
        os.makedirs(tools.IMAGES_DIR, exist_ok=True)
        for seg, im in ingest.attach_images(segs, images):
            seg.setdefault("images", [])
            name = "%s-I%02d.%s" % (seg["segment_id"], len(seg["images"]) + 1, im["ext"])
            with open(os.path.join(tools.IMAGES_DIR, name), "wb") as f:
                f.write(im["data"])
            seg["images"].append(name)
        tools.remove_upload(buoi)          # nạp lại cùng số buổi thì dọn ảnh cũ
        tools.add_upload(segs)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    names = [n for sg in segs for n in sg.get("images", [])]
    return {"buoi": buoi, "ten": segs[0]["session"], "so_doan": len(segs), "doan": [s["segment_id"] for s in segs],
            "so_anh": len(names), "anh": names}


@app.get("/api/images/{name}")
def get_image(name: str):
    """Ảnh đã trích từ tài liệu nạp (tên dạng D10-S02-I01.jpg)."""
    if not re.fullmatch(r"D\d{2}-S\d{2,3}-I\d{2,3}\.(jpg|png)", name):
        raise HTTPException(404, "không có ảnh")
    path = os.path.join(tools.IMAGES_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(404, "không có ảnh")
    return FileResponse(path)


@app.delete("/api/kho/{buoi}")
def kho_delete(buoi: int):
    """Xoá tài liệu đã nạp của một buổi (buổi 1–9 của kho gốc không xoá được)."""
    if buoi < 10:
        raise HTTPException(403, "không xoá được kho gốc")
    n = tools.remove_upload(buoi)
    if not n:
        raise HTTPException(404, "không có tài liệu nạp ở buổi %d" % buoi)
    return {"da_xoa": n}


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
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save_state()
    return {"created": True, "script": _script_public(SCRIPTS[script_id])}


@app.get("/api/scripts")
def list_scripts():
    out = []
    for sc in reversed(list(SCRIPTS.values())):
        out.append({
            "script_id": sc["script_id"], "buoi": sc["buoi"], "stage": sc["stage"], "status": sc["status"],
            "tong_cau": len(sc.get("claims") or []), "created_at": sc.get("created_at", ""),
        })
    return out


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
    _save_state()
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
    _save_state()
    return dict(_script_public(sc), vua_chap_nhan=n)


@app.post("/api/scripts/{script_id}/submit")
def script_submit(script_id: str):
    sc = _get_script(script_id)
    left = sum(1 for c in sc["claims"] if c["quyet_dinh"] == "chua_quyet")
    if left:
        raise HTTPException(409, "còn %d câu chưa quyết định" % left)
    res = tools.submit_for_review({"kind": "script", "buoi": sc["buoi"], "claims": sc["claims"]})
    sc["stage"], sc["status"], sc["review_id"] = "da_ra_soat", res["status"], res["draft_id"]
    _save_state()
    return _script_public(sc)


# ------------------------------------------------------------ luồng chính: tạo slide / quiz (không duyệt)

JOBS = {}
VOICE_SAMPLE = "Xin chào, đây là giọng đọc thuyết trình của bạn. Bài giảng sẽ được đọc rõ ràng, tự nhiên và dễ nghe."
SLIDE_STEPS = [("doc", "Đọc tài liệu & chọn đoạn nguồn"), ("viet", "AI soạn slide và tự kiểm với nguồn"),
               ("anh", "Chọn ảnh minh hoạ từ tài liệu"), ("giong", "Thu giọng đọc thuyết trình"),
               ("dung", "Dựng bản trình chiếu, PPTX và gói tải về")]
QUIZ_STEPS = [("doc", "Đọc tài liệu & chọn đoạn nguồn"), ("viet", "AI soạn câu hỏi và tự kiểm với nguồn"),
              ("dung", "Xuất PDF đề thi và PDF đáp án")]


class DeckJob(BaseModel):
    buoi: int
    chu_de: str = ""
    so_luong: int = 6
    mau: str = "Học thuật"
    voice: str = "vi-VN-HoaiMyNeural"
    rate: str = "+0%"
    dung_anh: bool = True            # chèn ảnh trích từ tài liệu vào slide
    co_giong: bool = True            # thu giọng đọc


class QuizJob(BaseModel):
    buoi: int
    chu_de: str = ""
    so_luong: int = 8


def _job_new(kind, steps):
    jid = "job-" + uuid.uuid4().hex[:8]
    JOBS[jid] = {"job_id": jid, "kind": kind, "status": "running", "t0": time.time(), "error": None, "draft_id": None,
                 "steps": [{"id": i, "label": l, "state": "pending", "detail": "", "t0": None, "t1": None} for i, l in steps],
                 "preview": [], "done": 0, "total": 0}
    return JOBS[jid]


def _step(job, sid, state, detail=None):
    for st in job["steps"]:
        if st["id"] == sid:
            st["state"] = state
            if detail is not None:
                st["detail"] = detail
            if state == "active" and not st["t0"]:
                st["t0"] = time.time()
            if state in ("done", "error"):
                st["t1"] = time.time()


def _live_detail():
    """Chi tiết thật của bước 'viet': đếm số lượt gọi model đang chạy trong khung trace."""
    n = len([e for e in list(tracing._case.get("events") or []) if e.get("kind") == "model"])
    if agent.PROGRESS["of"] > 1:
        return "Tài liệu dài: đang xử lý phần %d/%d (soạn rồi tự kiểm từng phần)…" % (agent.PROGRESS["batch"], agent.PROGRESS["of"])
    return ("Đang soạn nội dung từ đoạn nguồn…" if n <= 1 else
            "Đang tự kiểm từng ý với đoạn nguồn…" if n == 2 else "Phát hiện chỗ lệch nguồn — đang soạn lại bản chuẩn hơn…")


def _assign_images(items, enable=True):
    """Gắn ảnh của tài liệu vào slide: ưu tiên ảnh của đúng đoạn nguồn; slide chưa có ảnh nhận ảnh còn dư gần nhất. Mỗi ảnh dùng một lần."""
    for it in items:
        it["hinh_anh"] = []
    if not enable:
        return 0
    by_seg = {}
    for it in items:
        sid = it.get("segment_id", "")
        if sid and sid not in by_seg:
            by_seg[sid] = tools.get_segment_images(sid)
    used = set()
    for it in items:
        for n in by_seg.get(it.get("segment_id", ""), []):
            if n not in used:
                it["hinh_anh"] = [n]
                used.add(n)
                break
    buoi = {sid[1:3] for sid in by_seg if sid}
    spare = []
    for sg in tools.load_segments():
        if sg["segment_id"][1:3] in buoi:
            spare += [(sg["segment_id"], n) for n in tools.get_segment_images(sg["segment_id"]) if n not in used]

    def num(sid):
        m = re.search(r"-S(\d+)", sid or "")
        return int(m.group(1)) if m else 0
    for it in items:
        if not it["hinh_anh"] and spare:
            best = min(spare, key=lambda x: abs(num(x[0]) - num(it.get("segment_id", ""))))
            if abs(num(best[0]) - num(it.get("segment_id", ""))) <= 3:     # chỉ nhận ảnh cùng khu vực, không ghép ảnh lạc đề
                it["hinh_anh"] = [best[1]]
                spare.remove(best)
    return sum(len(it["hinh_anh"]) for it in items)


def _deck_options(d):
    return dict(d["options"], image_dir=tools.IMAGES_DIR)


def _rebuild_deck_files(d):
    """Dựng lại slides.html + slides.pptx + gói zip từ nội dung và giọng đọc hiện có của bản nháp."""
    out = os.path.join(DRAFT_DIR, d["draft_id"])
    files = d.setdefault("files", {})
    audio = {int(k.split("_")[1]): v for k, v in files.items() if k.startswith("audio_") and os.path.isfile(v)}
    title = d.get("tieu_de") or "Slide buổi %d — %s" % (d["buoi"], d["chu_de"])
    opts = _deck_options(d)
    files["slides_html"] = exporters.render_slides(d["items"], out, title, audio, opts)
    try:
        files["slides_pptx"] = pptx_export.export_pptx(d["items"], out, title, opts)
    except Exception as exc:       # PPTX lỗi không làm hỏng bản HTML
        d["pptx_error"] = str(exc)
    zpath = os.path.join(out, "slides_bundle.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(files["slides_html"], "slides.html")
        for p in audio.values():
            z.write(p, os.path.basename(p))
        if files.get("slides_pptx"):
            z.write(files["slides_pptx"], "slides.pptx")
    files["bundle_zip"] = zpath


def _est_minutes(items):
    words = sum(len(str(i.get("loi_thuyet_trinh", "")).split()) for i in items)
    return max(1, round(words / 2.6 / 60))


def _fail(job, exc):
    job["status"], job["error"] = "error", str(exc)
    for st in job["steps"]:
        if st["state"] == "active":
            _step(job, st["id"], "error", str(exc)[:300])


def _run_deck(job, body):
    try:
        segs = tools.segments_of_buoi(body.buoi)
        _step(job, "doc", "active")
        if not segs:
            raise RuntimeError("Kho chưa có tài liệu của buổi %d." % body.buoi)
        n_img = sum(len(s.get("images") or []) for s in segs)
        _step(job, "doc", "done", "%d đoạn nguồn · %d ảnh trong tài liệu" % (len(segs), n_img))
        _step(job, "viet", "active", "Đang soạn nội dung từ đoạn nguồn…")
        n = max(1, body.so_luong)
        res, trace = _traced("tạo slide", agent.create_from_doc, "slide", body.buoi, n, body.chu_de)
        data = res.get("data", {})
        if data.get("status") != "cho_duyet":
            raise RuntimeError(res["output"])
        items = data["items"]
        job["preview"] = [{"tieu_de": it.get("tieu_de", ""), "segment_id": it.get("segment_id", "")} for it in items]
        labels = data.get("nhan", [])
        ok = sum(1 for c in labels if c.get("nhan") == "KHOP_NGUON")
        _step(job, "viet", "done", "%d slide · %d/%d ý khớp nguồn" % (len(items), ok, len(labels)))
        _step(job, "anh", "active")
        k = _assign_images(items, body.dung_anh)
        _step(job, "anh", "done", ("Đã chọn %d ảnh minh hoạ từ tài liệu" % k) if k else
              ("Tài liệu không có ảnh dùng được — dùng bố cục chữ" if body.dung_anh else "Đã tắt ảnh minh hoạ"))
        draft_id = "draft-" + uuid.uuid4().hex[:8]
        voice = body.voice if body.voice in exporters.ALLOWED_VOICES else "vi-VN-HoaiMyNeural"
        rate = body.rate if body.rate in exporters.ALLOWED_RATES else "+0%"
        title = body.chu_de.strip() or data.get("chu_de") or "Bài giảng"
        opts = {"mau": body.mau, "voice": voice, "rate": rate, "ghi_chu": True, "dung_anh": body.dung_anh,
                "nguon": {s["segment_id"]: s["source_title"] for s in segs},
                "meta": ["Buổi %d" % body.buoi, "%d slide" % len(items), "≈ %d phút" % _est_minutes(items)]}
        d = {"draft_id": draft_id, "kind": "slide", "buoi": body.buoi, "chu_de": title, "tieu_de": title, "script_id": None,
             "options": opts, "items": items, "nhan": labels, "stage": "xong", "status": "xong",
             "files": {}, "audio_ts": {}, "voice_segments": {str(i): _build_voice_meta(it, None) for i, it in enumerate(items, 1)},
             "message": res["output"], "traces": [trace], "audio_errors": {},
             "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
        DRAFTS[draft_id] = d
        out = os.path.join(DRAFT_DIR, draft_id)
        if body.co_giong:
            _step(job, "giong", "active", "0/%d slide" % len(items))
            job["total"], job["done"] = len(items), 0

            def one(i):
                try:
                    d["files"]["audio_%d" % i] = exporters.synthesize_voice(i, items[i - 1]["loi_thuyet_trinh"], out, voice=voice, rate=rate)
                    d["audio_ts"][str(i)] = int(time.time() * 1000)
                except Exception as exc:
                    d["audio_errors"][str(i)] = str(exc)
                job["done"] += 1
                _step(job, "giong", "active", "%d/%d slide" % (job["done"], len(items)))
            with ThreadPoolExecutor(max_workers=2) as ex:
                list(ex.map(one, range(1, len(items) + 1)))
            miss = len(d["audio_errors"])
            _step(job, "giong", "done", ("Đã thu giọng %d slide" % (len(items) - miss)) +
                  (" · %d slide lỗi mạng, bản trình chiếu tự dùng giọng trình duyệt" % miss if miss else ""))
        else:
            _step(job, "giong", "done", "Đã tắt giọng đọc")
        d["_voice_used"] = [voice, rate]
        _step(job, "dung", "active")
        _rebuild_deck_files(d)
        _save_state()
        _step(job, "dung", "done", "Sẵn sàng trình chiếu và tải về" + (" (PPTX lỗi: %s)" % d["pptx_error"] if d.get("pptx_error") else ""))
        job["draft_id"], job["status"] = draft_id, "done"
    except Exception as exc:
        _fail(job, exc)


def _run_quiz(job, body):
    try:
        segs = tools.segments_of_buoi(body.buoi)
        _step(job, "doc", "active")
        if not segs:
            raise RuntimeError("Kho chưa có tài liệu của buổi %d." % body.buoi)
        _step(job, "doc", "done", "%d đoạn nguồn" % len(segs))
        _step(job, "viet", "active", "Đang soạn nội dung từ đoạn nguồn…")
        n = max(1, body.so_luong)
        res, trace = _traced("tạo quiz", agent.create_from_doc, "quiz", body.buoi, n, body.chu_de)
        data = res.get("data", {})
        if data.get("status") != "cho_duyet":
            raise RuntimeError(res["output"])
        items = data["items"]
        labels = data.get("nhan", [])
        ok = sum(1 for c in labels if c.get("nhan") == "KHOP_NGUON")
        job["preview"] = [{"tieu_de": it.get("de", ""), "segment_id": it.get("segment_id", "")} for it in items]
        _step(job, "viet", "done", "%d câu · %d/%d khớp nguồn" % (len(items), ok, len(labels)))
        _step(job, "dung", "active")
        title = body.chu_de.strip() or data.get("chu_de") or "Quiz"
        draft_id = "draft-" + uuid.uuid4().hex[:8]
        files = exporters.export_quiz_pdf(items, os.path.join(DRAFT_DIR, draft_id), "Quiz buổi %d — %s" % (body.buoi, title))
        DRAFTS[draft_id] = {"draft_id": draft_id, "kind": "quiz", "buoi": body.buoi, "chu_de": title, "script_id": None,
                            "options": {}, "items": items, "nhan": labels, "stage": "xong", "status": "xong",
                            "files": files, "audio_ts": {}, "voice_segments": {}, "message": res["output"], "traces": [trace],
                            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
        _save_state()
        _step(job, "dung", "done", "Đề thi và đáp án sẵn sàng")
        job["draft_id"], job["status"] = draft_id, "done"
    except Exception as exc:
        _fail(job, exc)


def _start(kind, steps, runner, body):
    if any(j["status"] == "running" for j in JOBS.values()):
        raise HTTPException(409, "đang có một tác vụ chạy, đợi xong rồi tạo tiếp")
    job = _job_new(kind, steps)
    threading.Thread(target=runner, args=(job, body), daemon=True).start()
    return {"job_id": job["job_id"]}


@app.post("/api/jobs/deck")
def job_deck(body: DeckJob):
    if body.buoi not in available_sessions():
        raise HTTPException(422, "kho chưa có buổi %d — hãy tải tài liệu lên trước" % body.buoi)
    return _start("deck", SLIDE_STEPS, _run_deck, body)


@app.post("/api/jobs/quiz")
def job_quiz(body: QuizJob):
    if body.buoi not in available_sessions():
        raise HTTPException(422, "kho chưa có buổi %d — hãy tải tài liệu lên trước" % body.buoi)
    return _start("quiz", QUIZ_STEPS, _run_quiz, body)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "không có tác vụ %s" % job_id)
    out = dict(job, elapsed_s=round(time.time() - job["t0"], 1))
    out["steps"] = [dict(st) for st in job["steps"]]
    if job["status"] == "running":
        for st in out["steps"]:
            if st["id"] == "viet" and st["state"] == "active":
                st["detail"] = _live_detail()
    if job["draft_id"]:
        out["draft"] = _public(DRAFTS[job["draft_id"]])
    return out


@app.get("/api/voice/preview")
def voice_preview(voice: str = "vi-VN-HoaiMyNeural", rate: str = "+0%"):
    """Nghe thử giọng đọc (đoạn mẫu ngắn, lưu đệm theo giọng + tốc độ)."""
    if voice not in exporters.ALLOWED_VOICES or rate not in exporters.ALLOWED_RATES:
        raise HTTPException(422, "giọng hoặc tốc độ không hợp lệ")
    out = os.path.join(DRAFT_DIR, "_preview", "%s_%s" % (voice, rate.replace("%", "p").replace("+", "n").replace("-", "m")))
    path = os.path.join(out, "slide_1.mp3")
    if not os.path.isfile(path):
        try:
            exporters.synthesize_voice(1, VOICE_SAMPLE, out, voice=voice, rate=rate)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc))
    return FileResponse(path, media_type="audio/mpeg")


_DL_NAMES = {"slides_html": "slides.html", "slides_pptx": "slides.pptx", "bundle_zip": "slides_bundle.zip",
             "exam_pdf": "quiz_de_thi.pdf", "answer_pdf": "quiz_dap_an.pdf"}


@app.get("/api/drafts/{draft_id}/files/{name}")
def download(draft_id: str, name: str, dl: int = 0):
    d = _get(draft_id)
    path = d["files"].get(name)
    if not path:    # cũng cho tải theo tên file thật (vd slide_1.mp3, vì HTML slide tham chiếu audio theo tên này)
        path = next((p for p in d["files"].values() if os.path.basename(p) == name), None)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "không có file %s" % name)
    root = os.path.realpath(os.path.join(DRAFT_DIR, draft_id))
    if not os.path.realpath(path).startswith(root):
        raise HTTPException(403, "ngoài thư mục bản nháp")
    if dl:
        return FileResponse(path, filename=_DL_NAMES.get(name, os.path.basename(path)))
    return FileResponse(path)


# Giao diện tĩnh (thư mục ui/ ở gốc repo) phục vụ cùng origin với API: http://localhost:8000/ui/
UI_DIR = os.path.join(ROOT, "ui")
if os.path.isdir(UI_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

_load_state()
