"""Standalone HTML slide deck from a script + its source document, one renderer per slide frame
(see app/edu/slide_frame.py for the framework and its rationale).

* fixed 1280×720 stage scaled to the window, so the preview, the projector and fullscreen look the same
* grid: 72px margins, eyebrow (section) + assertion title, evidence area, footer with source pages + n/N
* frames: cover · agenda · bullets · image_text · table · comparison · process · key_fact · summary · check · end
* narration per slide (if voiced): ▶ plays, captions follow the A1..An markers and highlight the matching
  point, "Tự chạy" plays the whole deck; ← → Space navigate, F fullscreen, N notes, A shows the quiz answer
Every text value is html-escaped; no external dependency except the web font (falls back to system-ui).
"""
from __future__ import annotations

import json
from html import escape
from typing import Dict, List, Optional

from app.edu import storage
from app.edu.docparse.models import ParsedDocument
from app.edu.scripts.models import Script, ScriptSlide

CSS = """
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0b1414;overflow:hidden;
 font-family:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.viewport{position:fixed;inset:0 0 56px 0;display:grid;place-items:center}
.stage{position:relative;width:1280px;height:720px;transform-origin:center;flex:none}
.slide{position:absolute;inset:0;display:none;flex-direction:column;padding:56px 72px 0;background:#fff;color:#0f1f1e;overflow:hidden}
.slide.on{display:flex}
.eyebrow{font-size:15px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#0f766e;margin:0 0 10px;min-height:18px}
.slide h1{margin:0;font-size:42px;line-height:1.18;font-weight:700;letter-spacing:-.015em;max-width:1050px;text-wrap:balance}
.content{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;padding:28px 0 20px}
.foot{height:52px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid #e3ebea;color:#6b7c7a;font-size:14px}
.foot b{color:#0f766e;font-weight:600}
.progress{position:absolute;left:0;top:0;height:5px;background:#0f766e}
/* points */
ul.pts{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:22px}
ul.pts li{font-size:28px;line-height:1.38;padding-left:36px;position:relative;transition:color .2s}
ul.pts li::before{content:"";position:absolute;left:4px;top:.5em;width:13px;height:13px;border-radius:4px;background:#0f766e}
ul.pts.big li{font-size:34px}
li.now,.card.now,.step.now{color:#0f766e}li.now{font-weight:600}
/* evidence */
.split{display:grid;grid-template-columns:5fr 6fr;gap:56px;align-items:center;height:100%}
figure{margin:0;display:flex;flex-direction:column;gap:10px;min-height:0;height:100%;justify-content:center}
figure img{max-width:100%;max-height:430px;object-fit:contain;border-radius:12px;background:#f3f7f6;align-self:center}
figcaption{font-size:14px;color:#5b6b6a;text-align:center}
.tbl{overflow:hidden;border:1px solid #d5e1df;border-radius:12px;align-self:flex-start;max-width:100%;min-width:min(640px,100%)}
.tbl table{width:100%}
table{border-collapse:collapse;font-size:20px}td,th{border-top:1px solid #e3ebea;padding:10px 18px;text-align:left;vertical-align:top}
th{background:#e6f4f2;color:#0b4f4a;font-weight:700;border-top:0}tr:nth-child(even) td{background:#fafcfc}
.tbl.small table{font-size:16px}.tbl.small td,.tbl.small th{padding:7px 12px}
.takeaway{margin-top:22px;padding:14px 20px;border-left:5px solid #0f766e;background:#f0f8f7;border-radius:0 10px 10px 0;font-size:22px;font-weight:600}
/* comparison */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:32px}
.card{border:1px solid #d5e1df;border-radius:16px;padding:26px 30px;background:#fbfdfd}
.card h2{margin:0 0 16px;font-size:26px;color:#0f766e}.card:nth-child(2) h2{color:#9a3412}
.card ul{margin:0;padding-left:22px;display:flex;flex-direction:column;gap:12px;font-size:22px;line-height:1.4}
/* process */
.steps{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:20px;position:relative}
.steps::before{content:"";position:absolute;left:40px;right:40px;top:28px;height:3px;background:#cfe3e0}
.step{position:relative;display:flex;flex-direction:column;gap:12px}
.step i{width:56px;height:56px;border-radius:50%;background:#0f766e;color:#fff;font-style:normal;font-weight:700;font-size:24px;display:grid;place-items:center;box-shadow:0 0 0 8px #fff}
.step b{font-size:22px;line-height:1.25}.step span{font-size:18px;line-height:1.45;color:#43524f}
/* key fact */
.fact{display:flex;flex-direction:column;align-items:flex-start;gap:20px}
.fact .val{font-size:76px;line-height:1.05;font-weight:700;color:#0f766e;letter-spacing:-.02em}
.fact p{margin:0;font-size:28px;line-height:1.45;max-width:980px}
/* agenda + summary */
ol.agenda{margin:0;padding:0;list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:18px 40px;counter-reset:a}
ol.agenda li{counter-increment:a;display:flex;gap:18px;align-items:baseline;font-size:25px;line-height:1.35;padding:14px 0;border-bottom:1px solid #e3ebea}
ol.agenda li::before{content:counter(a,decimal-leading-zero);font-weight:700;color:#0f766e;font-size:22px;font-variant-numeric:tabular-nums}
ul.check{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:20px}
ul.check li{display:flex;gap:18px;font-size:27px;line-height:1.4}
ul.check svg{flex:none;margin-top:6px;color:#0f766e}
/* quick check */
.q{font-size:36px;line-height:1.35;font-weight:600;max-width:1040px;margin:0}
.ans{margin-top:30px;display:flex;gap:16px;align-items:center}
.ans button{font:inherit;font-size:20px;font-weight:600;padding:12px 22px;border-radius:10px;border:2px solid #0f766e;background:#fff;color:#0f766e;cursor:pointer}
.ans p{display:none;margin:0;font-size:28px;line-height:1.4;padding:14px 20px;background:#f0f8f7;border-radius:10px}
.ans.open p{display:block}.ans.open button{display:none}
/* cover / end */
.slide.cover{background:#0f766e;color:#fff;justify-content:center;padding:0 96px}
.slide.cover::after{content:"";position:absolute;right:-160px;top:-160px;width:560px;height:560px;border-radius:50%;background:#115e59}
.cover>*{position:relative;z-index:1}
.cover .eyebrow{color:#99f6e4}.cover h1{font-size:62px;max-width:980px}
.cover .meta{margin-top:28px;font-size:20px;color:#ccfbf1;display:flex;gap:24px;flex-wrap:wrap}
/* chrome */
.bar{position:fixed;left:0;right:0;bottom:0;height:56px;display:flex;align-items:center;gap:10px;padding:0 16px;background:#0b1414;color:#e6efee;font-size:15px}
.bar button{min-height:40px;min-width:40px;border:1px solid #344745;background:#121d1c;color:#e6efee;border-radius:8px;padding:0 14px;font:inherit;cursor:pointer}
.bar button:disabled{opacity:.4;cursor:default}
.bar button:focus-visible,.ans button:focus-visible{outline:3px solid #5eead4;outline-offset:2px}.bar button[aria-pressed=true]{background:#0f766e;border-color:#0f766e}
.cap{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c4d2d0}.num{font-variant-numeric:tabular-nums;color:#93a5a3;min-width:56px;text-align:center}
.notes{position:fixed;right:16px;bottom:68px;width:min(560px,92vw);max-height:60vh;overflow:auto;background:#121d1c;color:#e6efee;border:1px solid #344745;border-radius:12px;padding:16px;display:none;font-size:15px;line-height:1.55;white-space:pre-wrap;z-index:5}
.notes.on{display:block}
@media (prefers-reduced-motion:no-preference){.slide.on .content>*{animation:rise .35s ease both}@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}}
"""

JS = """
const S=[...document.querySelectorAll('.slide')],T=JSON.parse(document.getElementById('tracks').textContent);
const stage=document.getElementById('stage'),vp=document.getElementById('vp');
const A=new Audio(),cap=document.getElementById('cap'),num=document.getElementById('num'),notes=document.getElementById('notes');
const play=document.getElementById('play'),auto=document.getElementById('auto');let i=0,autoOn=false;
function fit(){const s=Math.min(vp.clientWidth/1280,vp.clientHeight/720);stage.style.transform='scale('+s+')'}
addEventListener('resize',fit);fit();
function mark(seg){S[i].querySelectorAll('[data-seg]').forEach(e=>e.classList.toggle('now',!!seg&&e.dataset.seg.split(' ').includes(seg)))}
function show(n){i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,k)=>s.classList.toggle('on',k===i));num.textContent=(i+1)+' / '+S.length;
 A.pause();mark(null);const t=T[i];cap.textContent=t&&t.url?'':(t===null?'':'Slide này chưa có giọng đọc');notes.textContent=S[i].dataset.notes||'';
 play.disabled=!(t&&t.url);play.textContent='▶';if(history.replaceState)history.replaceState(null,'','#'+(i+1));
 if(t&&t.url){A.src=t.url;if(autoOn)A.play().catch(()=>{})}else if(autoOn){setTimeout(()=>{if(autoOn&&i<S.length-1)show(i+1)},3000)}}
A.addEventListener('play',()=>play.textContent='❚❚');A.addEventListener('pause',()=>play.textContent='▶');
A.addEventListener('timeupdate',()=>{const t=T[i];if(!t)return;const m=(t.markers||[]).find(m=>A.currentTime>=m.start&&A.currentTime<m.end);
 cap.textContent=m?m.text:'';mark(m&&m.segment);if(m&&m.reveal)S[i].querySelector('.ans')?.classList.add('open')});
A.addEventListener('ended',()=>{mark(null);if(autoOn&&i<S.length-1)setTimeout(()=>show(i+1),600)});
play.onclick=()=>A.paused?A.play():A.pause();auto.onclick=()=>{autoOn=!autoOn;auto.setAttribute('aria-pressed',autoOn);if(autoOn&&A.paused&&!play.disabled)A.play()};
document.getElementById('prev').onclick=()=>show(i-1);document.getElementById('next').onclick=()=>show(i+1);
document.getElementById('nb').onclick=()=>notes.classList.toggle('on');
document.querySelectorAll('.ans button').forEach(b=>b.onclick=()=>b.parentElement.classList.add('open'));
document.addEventListener('keydown',e=>{if(e.target.tagName==='BUTTON'&&(e.key===' '||e.key==='Enter'))return;
 if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();show(i+1)}
 else if(e.key==='ArrowLeft'||e.key==='PageUp')show(i-1);else if(e.key==='Home')show(0);else if(e.key==='End')show(S.length-1);
 else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen().catch(()=>{})}
 else if(e.key==='n'||e.key==='N')notes.classList.toggle('on');else if(e.key==='p'||e.key==='P')play.click();
 else if(e.key==='a'||e.key==='A')S[i].querySelector('.ans')?.classList.add('open')});
const go=()=>{const h=parseInt((location.hash||'').slice(1),10);if(isNaN(h)||h-1!==i||!S[i].classList.contains('on'))show(isNaN(h)?0:h-1)};
addEventListener('hashchange',go);go();
"""

CHECK_SVG = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/>'
             '<path d="m8 12 3 3 5-6"/></svg>')


def _included(seg) -> bool:
    return seg.quyet_dinh != "tu_choi_cau" and seg.nhan != "TU_CHOI"


def _e(x) -> str:
    return escape(str(x or ""))


def _li(items: List[tuple], cls: str = "pts") -> str:
    big = " big" if cls == "pts" and len(items) <= 2 else ""
    return f'<ul class="{cls}{big}">' + "".join(
        f'<li data-seg="{_e(seg)}">{CHECK_SVG if cls == "check" else ""}<span>{_e(t)}</span></li>' if cls == "check"
        else f'<li data-seg="{_e(seg)}">{_e(t)}</li>' for t, seg in items) + "</ul>"


def _points(s: ScriptSlide, body: list) -> List[tuple]:
    """On-screen points paired with the narration segment that explains them (for highlight while speaking)."""
    if s.y_chinh:
        return [(y, body[i].id if i < len(body) else "") for i, y in enumerate(s.y_chinh[:4])]
    return [(g.text, g.id) for g in body[:4]]


def _table(t, small: bool = False) -> str:
    rows: Dict[int, Dict[int, str]] = {}
    for c in t.cells:
        rows.setdefault(c.row, {})[c.col] = c.text
    out = []
    for r in sorted(rows)[:9]:
        tag = "th" if r == 0 else "td"
        out.append("<tr>" + "".join(f"<{tag}>{_e(rows[r].get(c, ''))}</{tag}>" for c in range(min(t.n_cols, 6))) + "</tr>")
    cls = "tbl small" if small or t.n_cols > 4 or len(rows) > 6 else "tbl"
    return f'<div class="{cls}"><table>{"".join(out)}</table></div>'


def _figure(s: ScriptSlide, doc: Optional[ParsedDocument]) -> str:
    for iid in s.image_ids:
        img = doc.images.get(iid) if doc else None
        if img and img.mime.startswith("image/") and img.mime not in ("image/x-wmf", "image/x-emf"):
            # (selection already filtered logos / page scans via slide_frame.is_figure)
            cap = img.alt or img.caption or ""
            caption = " · ".join(x for x in (cap, f"Hình {img.id}", f"trang {img.page}" if img.page else "") if x)
            return f'<figure><img src="{_e(img.url)}" alt="{_e(cap or img.id)}"><figcaption>{_e(caption)}</figcaption></figure>'
    return ""


def _body(s: ScriptSlide, doc: Optional[ParsedDocument], body: list) -> str:
    """Evidence area of one slide, by frame. Falls back to points when the frame data is missing."""
    lay, x = s.layout or "bullets", s.extra or {}
    ids = [g.id for g in body]
    if lay == "image_text":
        fig = _figure(s, doc)
        if fig:
            return f'<div class="split">{_li(_points(s, body)[:3])}{fig}</div>'
    if lay == "table":
        t = next((doc.tables[i] for i in s.table_ids if doc and i in doc.tables), None)
        if t:
            take = s.y_chinh[0] if s.y_chinh else ""
            return _table(t) + (f'<div class="takeaway" data-seg="{_e(ids[0] if ids else "")}">{_e(take)}</div>' if take else "")
    if lay == "comparison" and len(x.get("cot") or []) >= 2:
        cards = "".join(f'<div class="card" data-seg="{_e(ids[k] if k < len(ids) else "")}"><h2>{_e(c["ten"])}</h2><ul>'
                        + "".join(f"<li>{_e(y)}</li>" for y in c["y"]) + "</ul></div>"
                        for k, c in enumerate(x["cot"][:2]))
        return f'<div class="cols">{cards}</div>'
    if lay == "process" and len(x.get("buoc") or []) >= 3:
        steps = x["buoc"][:6]
        per = max(1, len(steps) // max(1, len(ids))) if ids else 1
        return '<div class="steps">' + "".join(
            f'<div class="step" data-seg="{_e(ids[min(k // per, len(ids) - 1)] if ids else "")}"><i>{k + 1}</i>'
            f'<b>{_e(b["ten"])}</b><span>{_e(b["mo_ta"])}</span></div>' for k, b in enumerate(steps)) + "</div>"
    if lay == "key_fact" and x.get("nhan_manh"):
        f = x["nhan_manh"]
        return (f'<div class="fact" data-seg="{_e(" ".join(ids))}"><div class="val">{_e(f["gia_tri"])}</div>'
                f'<p>{_e(f.get("giai_thich"))}</p></div>')
    if lay == "agenda":
        return '<ol class="agenda">' + "".join(f"<li>{_e(y)}</li>" for y in s.y_chinh[:6]) + "</ol>"
    if lay == "summary":
        return _li([(y, ids[k] if k < len(ids) else "") for k, y in enumerate(s.y_chinh[:4])], "check")
    if lay == "check" and x.get("cau_hoi"):
        return (f'<p class="q" data-seg="{_e(" ".join(g.id for g in s.doan if g.vai_tro == "dan_dat"))}">{_e(x["cau_hoi"])}</p>'
                f'<div class="ans" data-seg="{_e(" ".join(ids))}"><button type="button">Xem đáp án (A)</button>'
                f'<p>{_e(x.get("dap_an"))}</p></div>')
    fig = _figure(s, doc)                     # plain bullets (+ figure / table if one was attached)
    if fig:
        return f'<div class="split">{_li(_points(s, body)[:3])}{fig}</div>'
    t = next((doc.tables[i] for i in s.table_ids if doc and i in doc.tables), None)
    if t:
        return f'<div class="split">{_li(_points(s, body)[:3])}{_table(t, small=True)}</div>'
    return _li(_points(s, body))


def _pages(segs: list) -> str:
    pages = sorted({p for g in segs if g.nguon for p in (g.nguon.get("pages") or [])})
    if not pages:
        return ""
    return "Nguồn: tr. " + ", ".join(str(p) for p in pages[:6])


def render(sc: Script, doc: Optional[ParsedDocument]) -> str:
    shown = [s for s in sc.slides if any(_included(g) for g in s.doan) or s.y_chinh]
    total = len(shown) + 2
    sections, tracks = [], []
    seconds = sum((s.audio or {}).get("duration") or 0 for s in shown)
    meta = [f"{len(shown)} slide"] + ([f"{int(seconds // 60)} phút {int(seconds % 60)} giây giọng đọc"] if seconds else []) \
        + ([_e(doc.filename)] if doc else [])
    sections.append(f'<section class="slide cover" data-notes=""><p class="eyebrow">Bài giảng</p><h1>{_e(sc.title)}</h1>'
                    f'<div class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</div></section>')
    tracks.append(None)
    for n, s in enumerate(shown, start=2):
        segs = [g for g in s.doan if _included(g)]
        body = [g for g in segs if g.vai_tro != "dan_dat"]
        notes = "\n".join(f"{g.id} [{g.nhan}{' · ' + g.segment_id if g.segment_id else ''}] {g.text}" for g in segs)
        pct = round(100 * n / total, 2)
        sections.append(
            f'<section class="slide" data-layout="{_e(s.layout)}" data-notes="{_e(notes)}">'
            f'<div class="progress" style="width:{pct}%"></div>'
            f'<p class="eyebrow">{_e(s.phan)}</p><h1>{_e(s.tieu_de)}</h1>'
            f'<div class="content">{_body(s, doc, body)}</div>'
            f'<div class="foot"><span>{_e(_pages(segs))}</span><span><b>{n}</b> / {total}</span></div></section>')
        a = s.audio or {}
        text_by_id = {g.id: g.text for g in segs}
        answer_ids = {g.id for g in body} if s.layout == "check" else set()
        tracks.append({"url": a.get("url"), "duration": a.get("duration"),
                       "markers": [{**m, "text": text_by_id.get(m.get("segment"), ""),
                                    "reveal": m.get("segment") in answer_ids} for m in a.get("markers", [])]}
                      if a.get("url") else {"url": None})
    sections.append('<section class="slide cover" data-notes=""><p class="eyebrow">Kết thúc</p><h1>Cảm ơn các em đã lắng nghe</h1>'
                    f'<div class="meta"><span>{_e(sc.title)}</span></div></section>')
    tracks.append(None)
    data = json.dumps(tracks, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(sc.title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="viewport" id="vp"><main class="stage" id="stage">{''.join(sections)}</main></div>
<div class="notes" id="notes" role="region" aria-label="Ghi chú người nói"></div>
<div class="bar"><button id="prev" aria-label="Slide trước">‹</button><span class="num" id="num"></span><button id="next" aria-label="Slide sau">›</button>
<button id="play" aria-label="Phát giọng đọc">▶</button><button id="auto" aria-pressed="false">Tự chạy</button>
<span class="cap" id="cap" aria-live="polite"></span><button id="nb" aria-label="Ghi chú người nói">Ghi chú</button></div>
<script type="application/json" id="tracks">{data}</script><script>{JS}</script></body></html>"""


def save(sc: Script, doc: Optional[ParsedDocument]) -> str:
    path = storage.path("decks", f"{sc.id}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(sc, doc))
    return storage.url_for("decks", f"{sc.id}.html")
