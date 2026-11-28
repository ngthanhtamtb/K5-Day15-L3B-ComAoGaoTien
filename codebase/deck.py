"""Dựng bộ slide HTML một file, đẹp và đồng bộ: sân khấu 16:9 tự co giãn, 4 bảng màu, ảnh trích từ tài liệu,
hiệu ứng chuyển cảnh, phụ đề đồng bộ giọng đọc và nút điều hướng ẩn hai bên.

"Skill" thiết kế của app nằm ở đây (bảng màu, kiểu chữ, quy tắc bố cục) và trong .claude/skills/slide-design/SKILL.md.
Hàm chính: render_deck(items, out_dir, title, audio, options) -> đường dẫn slides.html.
"""
import base64
import mimetypes
import os
import re
from html import escape
from pathlib import Path
from urllib.parse import quote

# Bảng màu: mọi cặp chữ / nền đạt tỉ lệ tương phản ≥ 4.5:1.
THEMES = {
    "Học thuật": dict(bg="#EEF2F8", surface="#FFFFFF", ink="#0B1F3A", muted="#4B5E78", primary="#12355B",
                      accent="#0E9F9A", accent2="#F2A93B", line="#D5DDEA", cover1="#0B2545", cover2="#13508B",
                      cover_ink="#FFFFFF", chip_ink="#FFFFFF"),
    "Ấm áp": dict(bg="#FBF4EA", surface="#FFFDF9", ink="#2B1D14", muted="#6B5547", primary="#9A3F1D",
                  accent="#D9822B", accent2="#3F7D6B", line="#EBDCC8", cover1="#6E2A12", cover2="#B5562B",
                  cover_ink="#FFF9F0", chip_ink="#FFFFFF"),
    "Tối": dict(bg="#0B1220", surface="#15213A", ink="#EAF0FA", muted="#A3B3CC", primary="#7DB2FF",
                accent="#34D3C0", accent2="#FFC857", line="#25365A", cover1="#070C17", cover2="#17305E",
                cover_ink="#FFFFFF", chip_ink="#0B1220"),
    "Tối giản": dict(bg="#F4F4F2", surface="#FFFFFF", ink="#141414", muted="#555555", primary="#141414",
                     accent="#2563EB", accent2="#E5484D", line="#DDDDDA", cover1="#141414", cover2="#2B2B2B",
                     cover_ink="#FFFFFF", chip_ink="#FFFFFF"),
}
DEFAULT_THEME = "Học thuật"
THEME_ALIASES = {"AI20K chuẩn": DEFAULT_THEME}


def theme_of(options) -> tuple[str, dict]:
    name = (options or {}).get("mau")
    name = THEME_ALIASES.get(name, name)
    if name not in THEMES:
        name = DEFAULT_THEME
    return name, THEMES[name]


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+|\n+", (text or "").strip()) if p.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(Path(path).read_bytes()).decode("ascii"))


def image_paths(slide: dict, image_dir: str | None) -> list[str]:
    """Đường dẫn ảnh thật của slide (tối đa 2), bỏ tên file không tồn tại."""
    out = []
    for name in (slide.get("hinh_anh") or [])[:2]:
        if not image_dir:
            break
        path = os.path.join(image_dir, os.path.basename(str(name)))
        if os.path.isfile(path):
            out.append(path)
    return out


def layout_of(slide: dict, has_image: bool, index: int) -> str:
    if has_image:
        return "media-r" if index % 2 else "media-l"
    return "cards" if len(slide.get("y_chinh") or []) >= 3 else "focus"


CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;background:#05080f}
body{font-family:'Be Vietnam Pro','Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
#viewport{position:fixed;inset:0;overflow:hidden}
#stage{position:absolute;left:50%;top:50%;width:1280px;height:720px;transform-origin:center center;background:var(--bg);overflow:hidden;
  border-radius:6px;box-shadow:0 30px 80px rgba(0,0,0,.45)}
.slide{position:absolute;inset:0;padding:64px 80px 74px;opacity:0;visibility:hidden;transform:translateX(48px) scale(.99);
  transition:opacity .55s ease,transform .6s cubic-bezier(.2,.8,.2,1),visibility 0s .6s;display:flex;flex-direction:column;
  background:radial-gradient(900px 500px at 105% -10%,color-mix(in srgb,var(--accent) 14%,transparent),transparent 60%),
             radial-gradient(700px 420px at -10% 110%,color-mix(in srgb,var(--primary) 9%,transparent),transparent 60%),var(--bg)}
.slide.before{transform:translateX(-48px) scale(.99)}
.slide.active{opacity:1;visibility:visible;transform:none;transition:opacity .55s ease,transform .6s cubic-bezier(.2,.8,.2,1),visibility 0s}
.top{display:flex;align-items:center;gap:14px;margin-bottom:26px}
.eyebrow{font-size:17px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.num{margin-left:auto;font-size:16px;font-weight:600;color:var(--muted);font-variant-numeric:tabular-nums}
.bar{width:64px;height:6px;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
h2{font-size:52px;line-height:1.14;font-weight:800;letter-spacing:-.015em;color:var(--ink);max-width:1000px}
.dense h2{font-size:44px}
.body{flex:1;min-height:0;display:grid;gap:44px;align-items:center;margin-top:30px}
.media-r .body{grid-template-columns:1.08fr 1fr}.media-l .body{grid-template-columns:1fr 1.08fr}
.media-l figure{order:-1}
ul.pts{list-style:none;display:grid;gap:20px;counter-reset:p}
ul.pts li{display:grid;grid-template-columns:44px 1fr;gap:16px;align-items:start;font-size:29px;line-height:1.38;color:var(--ink)}
.dense ul.pts li{font-size:25px}
ul.pts li::before{content:counter(p);counter-increment:p;display:grid;place-items:center;width:44px;height:44px;border-radius:14px;
  background:var(--primary);color:var(--chip);font-size:20px;font-weight:700;margin-top:2px}
figure{position:relative;max-height:440px;display:grid;gap:14px;align-content:center}
figure .frame{position:relative;border-radius:22px;overflow:hidden;background:var(--surface);border:1px solid var(--line);
  box-shadow:0 18px 40px -18px rgba(8,20,45,.35);display:block;line-height:0}
figure img{width:100%;height:auto;max-height:400px;object-fit:contain;display:block;margin:0 auto}
.active figure img{animation:kb 16s ease-out both}
figcaption{position:absolute;left:14px;bottom:14px;background:color-mix(in srgb,var(--ink) 82%,transparent);color:var(--bg);font-size:14px;
  padding:6px 12px;border-radius:999px;font-weight:500}
.cards .body{grid-template-columns:repeat(3,1fr);align-items:start;gap:24px;margin-top:34px}
.card{min-height:300px;background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:30px 28px;display:flex;flex-direction:column;gap:16px;
  box-shadow:0 14px 30px -20px rgba(8,20,45,.35);position:relative;overflow:hidden}
.card::before{content:"";position:absolute;left:0;top:0;right:0;height:6px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.card .n{font-size:46px;font-weight:800;color:var(--accent);line-height:1}
.card p{font-size:25px;line-height:1.42;color:var(--ink)}
.focus .body{grid-template-columns:.9fr 1.25fr}
.kw{height:100%;max-height:400px;border-radius:26px;display:grid;place-items:center;text-align:center;padding:30px;position:relative;overflow:hidden;
  background:linear-gradient(145deg,var(--cover1),var(--cover2));color:var(--cover_ink)}
.kw::after{content:"";position:absolute;width:300px;height:300px;border-radius:50%;right:-90px;bottom:-110px;background:var(--accent);opacity:.28}
.kw::before{content:"";position:absolute;width:170px;height:170px;border-radius:50%;left:-60px;top:-60px;background:var(--accent2);opacity:.22}
.kw b{position:relative;z-index:1;font-size:46px;line-height:1.18;font-weight:800;letter-spacing:-.01em}
.foot{position:absolute;left:80px;right:80px;bottom:26px;display:flex;align-items:center;gap:12px;font-size:14px;color:var(--muted)}
.chip{background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary);padding:4px 12px;border-radius:999px;font-weight:600;font-family:'JetBrains Mono','Fira Code',ui-monospace,monospace;font-size:13px}
.foot .brand{margin-left:auto}
.cover,.closing{background:radial-gradient(900px 560px at 85% 10%,color-mix(in srgb,var(--accent) 38%,transparent),transparent 62%),
  radial-gradient(700px 500px at 0% 100%,color-mix(in srgb,var(--accent2) 22%,transparent),transparent 60%),
  linear-gradient(135deg,var(--cover1),var(--cover2));color:var(--cover_ink)}
.cover{justify-content:center}
.cover h1{font-size:68px;line-height:1.1;font-weight:800;letter-spacing:-.02em;max-width:960px;margin:22px 0 22px}
.cover .sub{font-size:26px;opacity:.88;max-width:820px;line-height:1.45}
.cover .tag{display:inline-flex;align-self:flex-start;gap:10px;align-items:center;padding:8px 18px;border-radius:999px;border:1.5px solid rgba(255,255,255,.4);
  font-size:18px;font-weight:600;letter-spacing:.04em}
.cover .meta{position:absolute;left:80px;bottom:44px;display:flex;gap:28px;font-size:18px;opacity:.82}
.cover .bar{width:96px;height:8px}
.closing h2{color:var(--cover_ink);font-size:56px}
.closing .body{grid-template-columns:1.3fr 1fr;align-items:start}
.closing ol{list-style:none;counter-reset:c;display:grid;gap:14px}
.closing ol li{counter-increment:c;font-size:26px;display:flex;gap:16px;align-items:baseline}
.closing ol li::before{content:counter(c,decimal-leading-zero);font-weight:800;color:var(--accent2);font-size:22px}
.closing .src{display:flex;flex-wrap:wrap;gap:10px;align-content:start}
.closing .src h3{width:100%;font-size:17px;letter-spacing:.14em;text-transform:uppercase;opacity:.75;margin-bottom:4px}
.closing .chip{background:rgba(255,255,255,.16);color:#fff;font-size:15px;padding:6px 14px}
.active .rv{animation:rise .65s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i,0)*.16s + .12s)}
@keyframes rise{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
@keyframes kb{from{transform:scale(1)}to{transform:scale(1.045)}}
#progress{position:absolute;left:0;top:0;height:5px;background:linear-gradient(90deg,var(--accent),var(--accent2));width:0;transition:width .5s ease;z-index:30}
.edge{position:absolute;top:0;bottom:0;width:120px;z-index:25;display:flex;align-items:center;opacity:0;transition:opacity .25s;border:0;background:none;cursor:pointer}
.edge.l{left:0;justify-content:flex-start;padding-left:22px}.edge.r{right:0;justify-content:flex-end;padding-right:22px}
.edge:hover,.edge:focus-visible{opacity:1}
.edge span{width:58px;height:58px;border-radius:50%;display:grid;place-items:center;background:rgba(10,20,40,.72);color:#fff;font-size:26px;
  backdrop-filter:blur(6px);box-shadow:0 8px 24px rgba(0,0,0,.35);transition:transform .2s}
.edge:hover span{transform:scale(1.1)}
.edge:disabled{display:none}
#cap{position:absolute;left:50%;bottom:76px;transform:translateX(-50%);max-width:1000px;width:max-content;z-index:26;text-align:center;
  background:rgba(8,14,28,.82);color:#fff;border-radius:16px;padding:12px 22px;font-size:23px;line-height:1.4;backdrop-filter:blur(8px);
  opacity:0;pointer-events:none;transition:opacity .25s}
#cap.on{opacity:1}
#bar{position:absolute;left:50%;bottom:16px;transform:translate(-50%,20px);z-index:28;display:flex;gap:6px;align-items:center;padding:7px 10px;
  border-radius:999px;background:rgba(8,14,28,.86);color:#fff;opacity:0;transition:opacity .25s,transform .25s;backdrop-filter:blur(10px);
  box-shadow:0 10px 30px rgba(0,0,0,.4)}
#stage:hover #bar,#bar:focus-within,#stage.show #bar{opacity:1;transform:translate(-50%,0)}
#bar button{border:0;background:transparent;color:#fff;height:40px;min-width:40px;padding:0 12px;border-radius:999px;cursor:pointer;font-weight:600;font-size:15px;font-family:inherit;display:flex;align-items:center;gap:6px}
#bar button:hover{background:rgba(255,255,255,.16)}
#bar button.on{background:var(--accent);color:#06121f}
#bar button.play{background:var(--accent);color:#06121f;width:46px;height:46px;justify-content:center;font-size:18px}
#pos{font-size:14px;min-width:64px;text-align:center;font-variant-numeric:tabular-nums;opacity:.9}
#seek{width:150px;accent-color:var(--accent2)}
#notice{position:absolute;top:18px;left:50%;transform:translateX(-50%);z-index:40;background:rgba(8,14,28,.9);color:#fff;padding:10px 18px;border-radius:12px;font-size:16px;opacity:0;transition:opacity .3s;pointer-events:none}
#notice.on{opacity:1}
@media (prefers-reduced-motion:reduce){.slide,.active .rv,.active figure img{transition:none!important;animation:none!important}}
"""

JS = r"""
const stage=document.getElementById('stage'),slides=[...document.querySelectorAll('.slide')];
const bar=document.getElementById('progress'),pos=document.getElementById('pos'),cap=document.getElementById('cap');
const prevB=document.getElementById('prev'),nextB=document.getElementById('next'),playB=document.getElementById('play');
const seek=document.getElementById('seek'),autoB=document.getElementById('auto'),ccB=document.getElementById('cc'),spdB=document.getElementById('spd');
const notice=document.getElementById('notice');
let cur=0,auto=true,cc=true,rate=1,audio=null,speaking=false,idle=null;
function scale(){const s=Math.min(innerWidth/1280,innerHeight/720);stage.style.transform='translate(-50%,-50%) scale('+s+')'}
addEventListener('resize',scale);scale();
function say(t){notice.textContent=t;notice.classList.add('on');clearTimeout(say.t);say.t=setTimeout(()=>notice.classList.remove('on'),2600)}
function sentencesOf(sl){return [...sl.querySelectorAll('template.sent')].map(t=>t.innerHTML)}
function setPlay(on){speaking=on;playB.textContent=on?'⏸':'▶'}
function stopVoice(){if(audio){audio.pause();audio.onended=audio.ontimeupdate=null;audio=null}
  if(window.speechSynthesis)speechSynthesis.cancel();setPlay(false);cap.classList.remove('on')}
function showCap(sents,i){if(!cc||!sents.length){cap.classList.remove('on');return}
  cap.innerHTML=sents[Math.max(0,Math.min(i,sents.length-1))];cap.classList.add('on')}
function show(n,play){
  n=Math.max(0,Math.min(n,slides.length-1));stopVoice();cur=n;
  slides.forEach((s,i)=>{s.classList.toggle('active',i===n);s.classList.toggle('before',i<n)});
  bar.style.width=((n+1)/slides.length*100)+'%';pos.textContent=(n+1)+' / '+slides.length;
  prevB.disabled=n===0;nextB.disabled=n===slides.length-1;history.replaceState(null,'','#'+(n+1));
  seek.value=0;if(play)speak();
}
function advance(){if(cur<slides.length-1)show(cur+1,true);else{auto=false;syncBtns()}}
function speak(){
  const sl=slides[cur],src=sl.dataset.audio,sents=sentencesOf(sl),me=cur;
  if(!sents.length){if(auto)setTimeout(()=>{if(cur===me&&auto)advance()},sl.classList.contains('cover')?3500:2500);return}
  setPlay(true);
  if(src){
    audio=new Audio(src);audio.playbackRate=rate;const w=sents.map(s=>s.length),tot=w.reduce((a,b)=>a+b,0);
    audio.ontimeupdate=()=>{if(!audio||!audio.duration)return;const f=audio.currentTime/audio.duration;seek.value=f*1000;
      let acc=0,k=0;for(;k<w.length-1;k++){acc+=w[k]/tot;if(f<acc)break}showCap(sents,k)};
    audio.onended=()=>{setPlay(false);if(auto)setTimeout(()=>{if(cur===me)advance()},700)};
    showCap(sents,0);audio.play().catch(()=>{setPlay(false);say('Bấm ▶ để nghe giọng đọc (trình duyệt chặn tự phát)')});
  }else if(window.speechSynthesis){
    const full=sl.dataset.text||sents.join(' ');const u=new SpeechSynthesisUtterance(full);u.lang='vi-VN';u.rate=rate;
    showCap(sents,0);
    u.onboundary=e=>{const f=e.charIndex/full.length;showCap(sents,Math.min(sents.length-1,Math.floor(f*sents.length)));seek.value=f*1000};
    u.onend=()=>{setPlay(false);if(auto)setTimeout(()=>{if(cur===me)advance()},700)};
    speechSynthesis.speak(u);say('Slide này chưa có file giọng — dùng giọng của trình duyệt')
  }else setPlay(false)
}
function toggle(){
  if(speaking){if(audio)audio.pause();else if(window.speechSynthesis)speechSynthesis.pause();setPlay(false)}
  else if(audio&&audio.currentTime>0&&!audio.ended){audio.play();setPlay(true)}
  else if(window.speechSynthesis&&speechSynthesis.paused){speechSynthesis.resume();setPlay(true)}
  else speak()}
function syncBtns(){autoB.classList.toggle('on',auto);ccB.classList.toggle('on',cc);spdB.textContent=rate+'×'}
playB.onclick=toggle;prevB.onclick=()=>show(cur-1,speaking);nextB.onclick=()=>show(cur+1,speaking);
autoB.onclick=()=>{auto=!auto;syncBtns();say(auto?'Tự chuyển slide khi đọc xong: BẬT':'Tự chuyển slide: TẮT')};
ccB.onclick=()=>{cc=!cc;syncBtns();if(!cc)cap.classList.remove('on')};
spdB.onclick=()=>{rate=rate===0.75?1:rate===1?1.25:rate===1.25?1.5:rate===1.5?2:0.75;if(audio)audio.playbackRate=rate;syncBtns()};
seek.oninput=()=>{if(audio&&audio.duration)audio.currentTime=audio.duration*seek.value/1000};
document.getElementById('fs').onclick=()=>{document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen()};
addEventListener('keydown',e=>{if(e.target.closest('input,textarea'))return;
  if(e.key==='ArrowRight'||e.key==='PageDown'){e.preventDefault();show(cur+1,speaking)}
  else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(cur-1,speaking)}
  else if(e.key===' '){e.preventDefault();toggle()}else if(e.key==='f'||e.key==='F')document.getElementById('fs').click();
  else if(e.key==='c'||e.key==='C')ccB.click();else if(e.key==='Home')show(0);else if(e.key==='End')show(slides.length-1)});
stage.addEventListener('mousemove',()=>{stage.classList.add('show');clearTimeout(idle);idle=setTimeout(()=>stage.classList.remove('show'),2600)});
syncBtns();show((parseInt(location.hash.slice(1))||1)-1);
"""


def _pts(slide: dict) -> list[str]:
    return [str(p) for p in (slide.get("y_chinh") or []) if str(p).strip()]


def render_deck(slides: list[dict], out_dir: str, title: str = "Slide", audio: dict | None = None,
                options: dict | None = None) -> str:
    """Ghi slides.html (một file; ảnh nhúng base64; giọng đọc là file .mp3 đặt cạnh, tham chiếu tương đối).
    options: mau (tên bảng màu), image_dir (thư mục ảnh), nguon {segment_id: tên nguồn}, phu_de, meta [chuỗi]."""
    options = options or {}
    _, theme = theme_of(options)
    image_dir = options.get("image_dir")
    sources = options.get("nguon") or {}
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe = lambda v: escape(str(v), quote=True)
    total = len(slides) + 2
    sections = []

    subtitle = options.get("phu_de") or "%d nội dung chính · có giọng thuyết trình" % len(slides)
    meta = "".join("<span>%s</span>" % safe(m) for m in (options.get("meta") or []))
    sections.append(
        '<section class="slide cover"><span class="tag rv" style="--i:0">● BÀI GIẢNG</span>'
        '<h1 class="rv" style="--i:1">%s</h1><div class="bar rv" style="--i:2"></div>'
        '<p class="sub rv" style="--i:3">%s</p><div class="meta rv" style="--i:4">%s</div></section>'
        % (safe(title), safe(subtitle), meta))

    for index, slide in enumerate(slides, 1):
        pts = _pts(slide)
        imgs = image_paths(slide, image_dir)
        layout = layout_of(slide, bool(imgs), index)
        dense = " dense" if sum(len(p) for p in pts) > 210 else ""
        kw = slide.get("tu_khoa") or ""
        sents = split_sentences(slide.get("loi_thuyet_trinh", "")) if options.get("ghi_chu", True) is not False else []
        tmpl = "".join('<template class="sent">%s</template>' % safe(s) for s in sents)
        attrs = ' data-text="%s"' % safe(slide.get("loi_thuyet_trinh", "")) if sents else ""
        if audio and index in audio:
            rel = os.path.relpath(Path(audio[index]).resolve(), directory.resolve())
            attrs += ' data-audio="%s"' % safe(quote(Path(rel).as_posix(), safe="/."))
        head = ('<div class="top"><span class="bar"></span><span class="eyebrow">%s</span><span class="num">%02d</span></div>'
                '<h2 class="rv" style="--i:0">%s</h2>'
                % (safe(kw if kw else "Nội dung %d" % index), index, safe(slide.get("tieu_de", ""))))
        if layout.startswith("media"):
            figs = "".join('<div class="frame"><img src="%s" alt="%s"></div>' % (_data_uri(p), safe(slide.get("tieu_de", "")))
                           for p in imgs)
            body = ('<div class="body"><ul class="pts">%s</ul><figure class="rv" style="--i:2">%s<figcaption>Hình trích từ tài liệu · %s</figcaption></figure></div>'
                    % ("".join('<li class="rv" style="--i:%d">%s</li>' % (i + 1, safe(p)) for i, p in enumerate(pts)),
                       figs, safe(slide.get("segment_id", ""))))
        elif layout == "cards":
            body = '<div class="body">%s</div>' % "".join(
                '<div class="card rv" style="--i:%d"><span class="n">%02d</span><p>%s</p></div>' % (i + 1, i + 1, safe(p))
                for i, p in enumerate(pts[:3]))
        else:
            body = ('<div class="body"><div class="kw rv" style="--i:1"><b>%s</b></div><ul class="pts">%s</ul></div>'
                    % (safe(kw or slide.get("tieu_de", "")),
                       "".join('<li class="rv" style="--i:%d">%s</li>' % (i + 2, safe(p)) for i, p in enumerate(pts))))
        foot = ('<div class="foot"><span class="chip">Nguồn %s</span><span>%s</span><span class="brand">%d / %d</span></div>'
                % (safe(slide.get("segment_id", "")), safe(sources.get(slide.get("segment_id"), "")), index + 1, total))
        sections.append('<section class="slide %s%s"%s>%s%s%s%s</section>' % (layout, dense, attrs, head, body, foot, tmpl))

    uniq = []
    for s in slides:
        if s.get("segment_id") and s["segment_id"] not in uniq:
            uniq.append(s["segment_id"])
    recap = "".join('<li class="rv" style="--i:%d">%s</li>' % (i + 1, safe(s.get("tieu_de", ""))) for i, s in enumerate(slides[:7]))
    chips = "".join('<span class="chip">%s</span>' % safe(u) for u in uniq)
    sections.append(
        '<section class="slide closing"><div class="top"><span class="bar"></span><span class="eyebrow" style="color:var(--accent2)">Tổng kết</span></div>'
        '<h2 class="rv" style="--i:0">Những điều cần nhớ</h2>'
        '<div class="body"><ol>%s</ol><div class="src rv" style="--i:3"><h3>Nguồn tài liệu</h3>%s</div></div></section>' % (recap, chips))

    css_vars = ":root{" + "".join("--%s:%s;" % (k, v) for k, v in theme.items()) + "--chip:%s}" % theme["chip_ink"]
    content = (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>" + safe(title) + "</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        "<style>" + css_vars + CSS + "</style></head><body>"
        '<div id="viewport"><div id="stage"><div id="progress"></div>' + "".join(sections) +
        '<button class="edge l" id="prev" type="button" aria-label="Slide trước"><span>‹</span></button>'
        '<button class="edge r" id="next" type="button" aria-label="Slide sau"><span>›</span></button>'
        '<div id="cap" aria-live="polite"></div><div id="notice"></div>'
        '<div id="bar" role="toolbar" aria-label="Điều khiển">'
        '<button class="play" id="play" type="button" aria-label="Phát / dừng giọng đọc">▶</button>'
        '<input id="seek" type="range" min="0" max="1000" value="0" aria-label="Tua giọng đọc"><span id="pos"></span>'
        '<button id="auto" type="button" title="Tự chuyển slide khi đọc xong">Tự chạy</button>'
        '<button id="cc" type="button" title="Phụ đề (C)">CC</button><button id="spd" type="button" title="Tốc độ đọc">1×</button>'
        '<button id="fs" type="button" title="Toàn màn hình (F)" aria-label="Toàn màn hình">⛶</button></div>'
        "</div></div><script>" + JS + "</script></body></html>")
    path = directory / "slides.html"
    path.write_text(content, encoding="utf-8")
    return str(path)
