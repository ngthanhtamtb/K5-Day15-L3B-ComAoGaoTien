/* Soạn bài giảng AI — luồng: Tài liệu → Slide → Quiz → Tải về. Không có bước duyệt. */
const API = location.protocol === "file:" ? "http://localhost:8000" : "";
const THEMES = {
  "Học thuật": ["#0B2545", "#0E9F9A", "#F2A93B", "#EEF2F8"],
  "Ấm áp": ["#6E2A12", "#D9822B", "#3F7D6B", "#FBF4EA"],
  "Tối": ["#070C17", "#34D3C0", "#FFC857", "#15213A"],
  "Tối giản": ["#141414", "#2563EB", "#E5484D", "#F4F4F2"],
};
const VOICES = [
  { id: "vi-VN-HoaiMyNeural", name: "Hoài My", desc: "Giọng nữ · ấm, rõ", av: "#0E9F9A" },
  { id: "vi-VN-NamMinhNeural", name: "Nam Minh", desc: "Giọng nam · trầm, chắc", av: "#12355B" },
];
const RATES = [["-15%", "Chậm"], ["+0%", "Bình thường"], ["+15%", "Nhanh"], ["+25%", "Rất nhanh"]];

const S = {
  docs: [], buoi: Number(localStorage.getItem("buoi")) || null, uploading: null,
  deck: { cfg: { chu_de: "", so: 6, mau: "Học thuật", voice: VOICES[0].id, rate: "+0%", anh: true, giong: true }, job: null, draft: null, ver: 1, busy: "" },
  quiz: { cfg: { chu_de: "", so: 8 }, job: null, draft: null, show: false },
  poll: null, ui: {},
};

/* ---------- tiện ích ---------- */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
async function api(method, path, body) {
  const r = await fetch(API + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  let d = null;
  try { d = await r.json(); } catch (e) { /* không phải JSON */ }
  if (!r.ok) throw new Error(d && d.detail ? (typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail)) : "Lỗi " + r.status);
  return d;
}
let toastT;
function toast(msg, err) {
  let t = document.getElementById("toast");
  if (!t) { t = h("div", { id: "toast", class: "toast" }); document.body.append(t); }
  t.textContent = msg; t.className = "toast on" + (err ? " err" : "");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("on"), err ? 5200 : 2600);
}
const route = () => (location.hash || "#/doc").slice(2) || "doc";
const go = (r) => { location.hash = "#/" + r; };
const fileUrl = (id, name, extra) => API + "/api/drafts/" + id + "/files/" + name + (extra || "");
const imgUrl = (n) => API + "/api/images/" + encodeURIComponent(n);
const docTitle = (d) => d.ten.replace(/^Buổi \d+ · /, "");
const curDoc = () => S.docs.find((d) => d.buoi === S.buoi);

/* ---------- khung chung ---------- */
function header() {
  const r = route();
  const st = (id, n, label, done) => h("button", { class: "step" + (r === id ? " on" : "") + (done && r !== id ? " done" : ""), onclick: () => go(id) },
    h("span", { class: "n" }, done && r !== id ? "✓" : String(n)), h("span", { class: "lbl" }, label));
  return h("header", { class: "top" }, h("div", { class: "top-in" },
    h("div", { class: "brand" }, h("div", { class: "logo" }, "✦"), "Soạn bài giảng AI"),
    h("nav", { class: "steps" }, st("doc", 1, "Tài liệu", !!S.buoi), st("slide", 2, "Tạo slide", !!S.deck.draft), st("quiz", 3, "Tạo quiz", !!S.quiz.draft))));
}
function render() {
  const r = route();
  const app = document.getElementById("app");
  app.replaceChildren(header(), h("main", { class: "shell" }, r === "slide" ? viewDeck() : r === "quiz" ? viewQuiz() : viewDocs()));
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => { if (route() === "doc") loadDocs().then(render); else render(); });

/* ---------- 1. Tài liệu ---------- */
async function loadDocs() {
  try { S.docs = (await api("GET", "/api/kho")).sort((a, b) => b.tai_len - a.tai_len || b.buoi - a.buoi); }
  catch (e) { toast("Không kết nối được máy chủ: " + e.message, true); S.docs = []; }
  if (!S.docs.some((d) => d.buoi === S.buoi)) S.buoi = (S.docs.find((d) => d.tai_len) || S.docs[0] || {}).buoi || null;
  if (S.buoi) localStorage.setItem("buoi", S.buoi);
}
function readB64(file) {
  return new Promise((ok, no) => {
    const fr = new FileReader();
    fr.onload = () => ok(String(fr.result).split(",")[1]);
    fr.onerror = () => no(new Error("không đọc được file"));
    fr.readAsDataURL(file);
  });
}
async function upload(file) {
  if (!file) return;
  S.uploading = file.name; render();
  try {
    const res = await api("POST", "/api/kho/upload", { filename: file.name, content_b64: await readB64(file) });
    S.buoi = res.buoi; localStorage.setItem("buoi", res.buoi);
    await loadDocs();
    toast("Đã nạp “" + file.name + "”: " + res.so_doan + " đoạn nguồn, " + res.so_anh + " ảnh");
  } catch (e) { toast(e.message, true); }
  S.uploading = null; render();
}
function viewDocs() {
  const input = h("input", { type: "file", accept: ".pdf,.docx,.pptx,.txt,.md", hidden: true, onchange: (e) => upload(e.target.files[0]) });
  const drop = h("div", {
    class: "drop", onclick: () => input.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files[0]); },
  }, input,
  h("div", { class: "ic" }, S.uploading ? "⏳" : "⬆"),
  h("h3", null, S.uploading ? "Đang đọc “" + S.uploading + "”…" : "Kéo thả hoặc bấm để tải tài liệu lên"),
  h("p", null, S.uploading ? "Trích chữ, cắt đoạn nguồn và lấy ảnh trong tài liệu" : "App sẽ đọc chữ và lấy luôn ảnh trong tài liệu để minh hoạ cho slide"),
  h("div", { class: "fmt" }, ["PDF", "DOCX", "PPTX", "TXT", "MD"].map((x) => h("span", { class: "chip" }, x))));
  const cards = S.docs.map((d) => {
    const imgs = d.anh || [];
    return h("div", { class: "card doc" + (d.buoi === S.buoi ? " sel" : ""), onclick: () => { S.buoi = d.buoi; localStorage.setItem("buoi", d.buoi); render(); } },
      d.tai_len ? h("button", { class: "btn sm ghost rm", title: "Xoá tài liệu", onclick: async (e) => {
        e.stopPropagation();
        if (!confirm("Xoá tài liệu này?")) return;
        try { await api("DELETE", "/api/kho/" + d.buoi); await loadDocs(); render(); } catch (er) { toast(er.message, true); }
      } }, "Xoá") : null,
      h("h4", null, docTitle(d)),
      h("div", { class: "meta" }, h("span", { class: "chip" }, d.so_doan + " đoạn nguồn"),
        imgs.length ? h("span", { class: "chip ok" }, "🖼 " + imgs.length + " ảnh") : h("span", { class: "chip" }, "không có ảnh"),
        h("span", { class: "chip" }, Math.max(1, Math.round(d.so_ky_tu / 1000)) + "k ký tự"),
        d.tai_len ? null : h("span", { class: "chip warn" }, "tài liệu mẫu")),
      h("p", { class: "pv" }, d.xem_truoc || ""),
      imgs.length ? h("div", { class: "thumbs" }, imgs.slice(0, 4).map((n) => h("img", { src: imgUrl(n), alt: "", loading: "lazy" })),
        imgs.length > 4 ? h("div", { class: "more" }, "+" + (imgs.length - 4)) : null) : null,
      h("div", { class: "tick" }, "✓"));
  });
  return h("div", null,
    h("div", { class: "hero" }, h("h1", null, "Bắt đầu từ tài liệu của bạn"),
      h("p", null, "Tải tài liệu lên, chọn một bài rồi để AI dựng slide có giọng thuyết trình và bộ quiz — mọi nội dung đều bám đoạn nguồn trong tài liệu.")),
    drop,
    h("div", { class: "section-t" }, h("h2", null, "Tài liệu đã có (" + S.docs.length + ")"), h("span", { class: "muted" }, "Bấm vào thẻ để chọn tài liệu dùng cho slide và quiz")),
    h("div", { class: "docs" }, cards),
    h("div", { class: "nav" }, h("span"), h("button", { class: "btn pri big", disabled: !S.buoi, onclick: () => go("slide") }, "Tiếp tục: Tạo slide →")));
}

/* ---------- tiến trình & tạo ---------- */
function stopPoll() { clearInterval(S.poll); S.poll = null; }
async function startJob(kind, body) {
  const st = S[kind === "deck" ? "deck" : "quiz"];
  st.draft = null; st.job = { status: "running", steps: [], preview: [], elapsed_s: 0 }; st.error = null;
  paintStage(kind);
  try {
    const { job_id } = await api("POST", "/api/jobs/" + kind, body);
    stopPoll();
    S.poll = setInterval(async () => {
      try {
        const j = await api("GET", "/api/jobs/" + job_id);
        st.job = j;
        if (j.status === "done") { stopPoll(); st.draft = j.draft; st.ver++; st.job = null; render(); toast(kind === "deck" ? "Slide đã sẵn sàng!" : "Quiz đã sẵn sàng!"); return; }
        if (j.status === "error") { stopPoll(); st.error = j.error; }
        paintStage(kind);
      } catch (e) { stopPoll(); st.error = e.message; st.job = null; paintStage(kind); }
    }, 800);
  } catch (e) { st.job = null; st.error = e.message; paintStage(kind); }
}
function progressPanel(st, title, n) {
  const j = st.job;
  const steps = j.steps || [];
  const total = steps.length || 1;
  let done = steps.filter((s) => s.state === "done").length;
  const act = steps.find((s) => s.state === "active");
  if (act && act.id === "giong" && j.total) done += j.done / j.total;
  else if (act) done += 0.35;
  const pct = Math.min(97, Math.round((done / total) * 100));
  const now = Date.now() / 1000;
  const pv = j.preview || [];
  return h("div", { class: "card prog" },
    h("h3", null, title), h("div", { class: "muted" }, "Đã chạy " + Math.round(j.elapsed_s || 0) + " giây — giữ nguyên tab này nhé"),
    h("div", { class: "bar" }, h("i", { style: "width:" + pct + "%" })),
    h("ul", { class: "tl" }, steps.map((s, i) => {
      const el = s.t0 ? Math.max(0, Math.round((s.t1 || now) - s.t0)) : null;
      return h("li", { class: s.state }, h("span", { class: "dot" }, s.state === "done" ? "✓" : s.state === "error" ? "!" : String(i + 1)),
        h("div", null, h("b", null, s.label), s.detail ? h("small", null, s.detail) : null),
        h("span", { class: "el" }, el != null && s.state !== "pending" ? el + "s" : ""));
    })),
    h("div", { class: "skel" }, Array.from({ length: Math.max(n, pv.length) }, (_, i) => pv[i]
      ? h("div", { class: "sk in", style: "animation-delay:" + i * 90 + "ms" }, h("small", null, (kindLabel(st) + " " + (i + 1)) + " · " + pv[i].segment_id), pv[i].tieu_de.slice(0, 70))
      : h("div", { class: "sk" }))));
}
const kindLabel = (st) => (st === S.deck ? "Slide" : "Câu");
function errBox(st) {
  return st.error ? h("div", { class: "err-box" }, "⚠ " + st.error, h("div", { style: "margin-top:6px;font-weight:400" }, "Kiểm tra lại tài liệu hoặc thử tạo lại — dữ liệu đã nạp vẫn còn.")) : null;
}
function paintStage(kind) {
  const el = S.ui[kind];
  if (!el || !el.isConnected) return;
  const st = kind === "deck" ? S.deck : S.quiz;
  const n = kind === "deck" ? st.cfg.so : st.cfg.so;
  let node;
  if (st.job) node = progressPanel(st, kind === "deck" ? "Đang dựng bộ slide của bạn…" : "Đang soạn bộ câu hỏi…", n);
  else if (st.draft) node = kind === "deck" ? deckResult() : quizResult();
  else node = h("div", { class: "card empty" }, h("div", { class: "big" }, kind === "deck" ? "🎬" : "📝"),
    h("h3", null, kind === "deck" ? "Slide của bạn sẽ hiện ở đây" : "Bộ quiz của bạn sẽ hiện ở đây"),
    h("p", null, kind === "deck" ? "Chọn bảng màu, giọng đọc rồi bấm “Tạo slide”." : "Chọn số câu rồi bấm “Tạo quiz”."));
  el.replaceChildren(...[errBox(st), node].filter(Boolean));
}

/* ---------- 2. Slide ---------- */
function noDoc() {
  return h("div", { class: "card empty", style: "margin-top:40px" }, h("div", { class: "big" }, "📄"), h("h3", null, "Chưa chọn tài liệu"),
    h("p", null, "Hãy tải tài liệu lên hoặc chọn một tài liệu có sẵn trước."), h("button", { class: "btn pri", style: "margin-top:18px", onclick: () => go("doc") }, "← Về bước Tài liệu"));
}
function stepper(get, set, min, max) {
  const b = h("b", null, String(get()));
  const upd = (v) => { set(Math.max(min, Math.min(max, v))); b.textContent = get(); };
  return h("div", { class: "stepper" }, h("button", { onclick: () => upd(get() - 1) }, "−"), b, h("button", { onclick: () => upd(get() + 1) }, "+"));
}
let previewAudio = null;
function playPreview(btn, voice, rate) {
  if (previewAudio) { previewAudio.pause(); previewAudio = null; }
  btn.textContent = "…";
  const a = new Audio(API + "/api/voice/preview?voice=" + encodeURIComponent(voice) + "&rate=" + encodeURIComponent(rate));
  previewAudio = a;
  a.onplaying = () => (btn.textContent = "■"); a.onended = () => (btn.textContent = "▶");
  a.onerror = () => { btn.textContent = "▶"; toast("Không nghe thử được giọng (cần mạng để tổng hợp giọng)", true); };
  a.play().catch(() => (btn.textContent = "▶"));
}
function viewDeck() {
  const doc = curDoc();
  if (!doc) return noDoc();
  const c = S.deck.cfg;
  const rateSel = h("select", { onchange: (e) => (c.rate = e.target.value) }, RATES.map(([v, l]) => h("option", { value: v, selected: v === c.rate }, l + " (" + v + ")")));
  const panel = h("div", { class: "card panel" }, h("h3", null, "Tuỳ chọn slide"),
    h("div", { class: "field" }, h("label", { class: "f" }, "Tài liệu"), h("div", { class: "chip" }, docTitle(doc).slice(0, 40)),
      h("span", { class: "muted", style: "font-size:13px;margin-left:8px" }, (doc.anh || []).length + " ảnh")),
    h("div", { class: "field" }, h("label", { class: "f" }, "Chủ đề muốn nhấn mạnh (tuỳ chọn)"),
      h("input", { type: "text", placeholder: "Để trống = dùng toàn bộ tài liệu", value: c.chu_de, oninput: (e) => (c.chu_de = e.target.value) })),
    h("div", { class: "field" }, h("label", { class: "f" }, "Số slide nội dung"), stepper(() => c.so, (v) => { c.so = v; }, 1, 999)),
    h("div", { class: "field" }, h("label", { class: "f" }, "Bảng màu"),
      h("div", { class: "themes" }, Object.entries(THEMES).map(([name, cols]) => h("button", { class: "theme" + (c.mau === name ? " on" : ""), onclick: (e) => {
        c.mau = name; e.currentTarget.parentNode.querySelectorAll(".theme").forEach((t) => t.classList.remove("on")); e.currentTarget.classList.add("on");
      } }, h("div", { class: "sw" }, cols.map((x) => h("i", { style: "background:" + x }))), h("span", null, name))))),
    h("div", { class: "field" }, h("label", { class: "f" }, "Giọng đọc thuyết trình"),
      h("div", { class: "voices" }, VOICES.map((v) => h("div", { class: "voice" + (c.voice === v.id ? " on" : ""), role: "button", tabindex: 0, onclick: (e) => {
        c.voice = v.id; e.currentTarget.parentNode.querySelectorAll(".voice").forEach((x) => x.classList.remove("on")); e.currentTarget.classList.add("on");
      } }, h("div", { class: "av", style: "background:" + v.av }, v.name[0]), h("div", null, h("b", null, v.name), h("small", null, v.desc)),
      h("button", { class: "pl", title: "Nghe thử", onclick: (e) => { e.stopPropagation(); playPreview(e.currentTarget, v.id, c.rate); } }, "▶"))))),
    h("div", { class: "field" }, h("label", { class: "f" }, "Tốc độ đọc"), rateSel),
    toggleRow("Ảnh minh hoạ từ tài liệu", (doc.anh || []).length ? "Chèn " + doc.anh.length + " ảnh có trong tài liệu vào slide phù hợp" : "Tài liệu này không có ảnh", c.anh, (v) => (c.anh = v)),
    toggleRow("Thu giọng thuyết trình", "Mỗi slide có file giọng và phụ đề chạy theo", c.giong, (v) => (c.giong = v)),
    h("button", { class: "btn pri big", style: "width:100%;margin-top:8px", onclick: () => {
      if (S.poll) return toast("Đang có tác vụ chạy", true);
      startJob("deck", { buoi: S.buoi, chu_de: c.chu_de, so_luong: c.so, mau: c.mau, voice: c.voice, rate: c.rate, dung_anh: c.anh, co_giong: c.giong });
    } }, S.deck.draft ? "↻ Tạo lại slide" : "✦ Tạo slide"));
  const stage = h("div", { class: "stage" });
  S.ui.deck = stage;
  setTimeout(() => paintStage("deck"));
  return h("div", null, h("div", { class: "hero" }, h("h1", null, "Tạo slide có giọng thuyết trình"),
    h("p", null, "AI soạn nội dung bám nguồn, chọn ảnh từ tài liệu để minh hoạ, rồi thu giọng đọc cho từng slide.")),
  h("div", { class: "studio" }, panel, stage),
  h("div", { class: "nav" }, h("button", { class: "btn", onclick: () => go("doc") }, "← Tài liệu"), h("button", { class: "btn pri", onclick: () => go("quiz") }, "Tiếp: Tạo quiz →")));
}
function toggleRow(title, sub, val, set) {
  const inp = h("input", { type: "checkbox", checked: val, onchange: (e) => set(e.target.checked) });
  return h("div", { class: "toggle" }, h("div", null, h("b", { style: "font-size:14.5px" }, title), h("small", null, sub)), h("div", { class: "sw-t" }, inp, h("i")));
}
function sourceBtn(sid) {
  const box = h("div", { class: "srcbox" });
  const btn = h("button", { class: "btn sm ghost", onclick: async () => {
    if (box.style.display === "block") { box.style.display = "none"; return; }
    try { const s = await api("GET", "/api/segments/" + sid); box.textContent = "“" + s.full_text + "”"; box.style.display = "block"; }
    catch (e) { toast(e.message, true); }
  } }, "📎 " + sid + " · xem đoạn nguồn");
  return h("div", null, btn, box);
}
function deckResult() {
  const d = S.deck.draft;
  const f = d.files || {};
  const dlBtn = (name, label, pri) => f[name] ? h("a", { class: "btn" + (pri ? " pri" : ""), href: fileUrl(d.draft_id, name, "?dl=1") }, label) : null;
  const nAudio = Object.keys(f).filter((k) => k.startsWith("audio_")).length;
  const nImg = d.items.reduce((s, it) => s + (it.hinh_anh || []).length, 0);
  const url = fileUrl(d.draft_id, "slides_html", "?v=" + S.deck.ver);
  const meta = (d.options && d.options.meta) || [];
  return h("div", null,
    h("div", { class: "card", style: "overflow:hidden" },
      h("div", { class: "res-head" }, h("h3", null, "🎬 " + (d.tieu_de || d.chu_de)),
        meta.map((m) => h("span", { class: "chip" }, m)), h("span", { class: "chip ok" }, "🖼 " + nImg + " ảnh"),
        h("span", { class: nAudio === d.items.length ? "chip ok" : "chip warn" }, "🔊 " + nAudio + "/" + d.items.length + " giọng"),
        h("div", { class: "dl" }, dlBtn("slides_pptx", "⬇ PPTX", true), dlBtn("slides_html", "⬇ HTML"), dlBtn("bundle_zip", "⬇ ZIP (kèm giọng)"),
          h("a", { class: "btn", href: url, target: "_blank" }, "⛶ Mở toàn màn hình"))),
      h("iframe", { class: "player", src: url, allow: "fullscreen; autoplay", allowfullscreen: true, title: "Bản trình chiếu" })),
    h("div", { class: "muted", style: "margin:10px 4px 0;font-size:13.5px" }, "Mẹo: di chuột vào mép trái / phải để chuyển slide · phím Space phát giọng · F toàn màn hình · C bật tắt phụ đề."),
    voiceStudio(d));
}
async function regen(label, body) {
  const d = S.deck.draft;
  S.deck.busy = label; toast(label + "…");
  try {
    const res = await api("POST", "/api/drafts/" + d.draft_id + "/voice", body);
    S.deck.draft = res.draft; S.deck.ver++;
    S.deck.busy = ""; paintStage("deck"); toast("Đã cập nhật giọng đọc");
  } catch (e) { S.deck.busy = ""; paintStage("deck"); toast(e.message, true); }
}
function voiceStudio(d) {
  const o = d.options || {};
  let voice = o.voice || VOICES[0].id, rate = o.rate || "+0%";
  const busy = !!S.deck.busy;
  const vSel = h("select", { onchange: (e) => (voice = e.target.value) }, VOICES.map((v) => h("option", { value: v.id, selected: v.id === voice }, v.name + " — " + v.desc)));
  const rSel = h("select", { onchange: (e) => (rate = e.target.value) }, RATES.map(([v, l]) => h("option", { value: v, selected: v === rate }, l + " (" + v + ")")));
  const rows = d.items.map((it, i) => {
    const n = i + 1, has = !!(d.files || {})["audio_" + n];
    const ta = h("textarea", { rows: 5 }, it.loi_thuyet_trinh);
    return h("div", { class: "vrow" }, h("div", { class: "no" }, String(n)),
      h("div", null, h("h4", null, it.tieu_de),
        has ? h("audio", { controls: true, preload: "none", src: fileUrl(d.draft_id, "audio_" + n, "?v=" + ((d.audio_ts || {})[n] || S.deck.ver)) })
          : h("div", { class: "chip warn", style: "margin-bottom:8px" }, "Chưa có file giọng — slide sẽ dùng giọng của trình duyệt"),
        ta,
        h("div", { class: "acts" }, h("button", { class: "btn sm pri", disabled: busy, onclick: () => regen("Đang thu lại giọng slide " + n,
          { slide_index: n, loi_thuyet_trinh: ta.value, voice, rate }) }, "🎙 Lưu lời & thu lại giọng"), sourceBtn(it.segment_id))));
  });
  return h("div", { class: "card vs" }, h("h3", null, "🎙 Giọng thuyết trình từng slide"),
    h("div", { class: "sub" }, "Nghe từng slide, sửa lời nếu muốn rồi thu lại. Đổi giọng hoặc tốc độ sẽ áp dụng cho cả bộ."),
    h("div", { class: "vbar" }, h("div", null, h("label", { class: "f" }, "Giọng đọc"), vSel), h("div", null, h("label", { class: "f" }, "Tốc độ"), rSel),
      h("button", { class: "btn pri", disabled: busy, onclick: () => regen("Đang thu lại giọng cả bộ", { voice, rate }) }, busy ? "⏳ " + S.deck.busy : "🔁 Thu lại toàn bộ giọng")),
    rows);
}

/* ---------- 3. Quiz ---------- */
function viewQuiz() {
  const doc = curDoc();
  if (!doc) return noDoc();
  const c = S.quiz.cfg;
  const panel = h("div", { class: "card panel" }, h("h3", null, "Tuỳ chọn quiz"),
    h("div", { class: "field" }, h("label", { class: "f" }, "Tài liệu"), h("div", { class: "chip" }, docTitle(doc).slice(0, 40))),
    h("div", { class: "field" }, h("label", { class: "f" }, "Chủ đề muốn tập trung (tuỳ chọn)"),
      h("input", { type: "text", placeholder: "Để trống = phủ toàn bộ tài liệu", value: c.chu_de, oninput: (e) => (c.chu_de = e.target.value) })),
    h("div", { class: "field" }, h("label", { class: "f" }, "Số câu trắc nghiệm"), stepper(() => c.so, (v) => { c.so = v; }, 1, 999)),
    h("div", { class: "muted", style: "font-size:13.5px;margin-bottom:18px" }, "Mỗi câu có 4 phương án A–D, đúng 1 đáp án, kèm giải thích và đoạn nguồn trích dẫn. Xuất ra 2 file PDF: đề thi và đáp án."),
    h("button", { class: "btn pri big", style: "width:100%", onclick: () => {
      if (S.poll) return toast("Đang có tác vụ chạy", true);
      startJob("quiz", { buoi: S.buoi, chu_de: c.chu_de, so_luong: c.so });
    } }, S.quiz.draft ? "↻ Tạo lại quiz" : "✦ Tạo quiz"));
  const stage = h("div", { class: "stage" });
  S.ui.quiz = stage;
  setTimeout(() => paintStage("quiz"));
  return h("div", null, h("div", { class: "hero" }, h("h1", null, "Tạo bộ quiz từ tài liệu"),
    h("p", null, "Câu hỏi được tự kiểm với đoạn nguồn; tải về PDF đề thi để in và PDF đáp án cho giảng viên.")),
  h("div", { class: "studio" }, panel, stage),
  h("div", { class: "nav" }, h("button", { class: "btn", onclick: () => go("slide") }, "← Tạo slide"), h("span")));
}
function quizResult() {
  const d = S.quiz.draft, f = d.files || {};
  const labels = d.nhan && d.nhan.length === d.items.length ? d.nhan : null;
  const dl = (name, label, pri) => f[name] ? h("a", { class: "btn" + (pri ? " pri" : ""), href: fileUrl(d.draft_id, name, "?dl=1") }, label) : null;
  const list = h("div", { class: S.quiz.show ? "show" : "" }, d.items.map((q, i) => {
    const lb = labels && labels[i];
    return h("div", { class: "card q" }, h("div", { class: "qh" }, h("div", { class: "qn" }, String(i + 1)), h("h4", null, q.de)),
      h("div", { class: "opts" }, "ABCD".split("").map((L) => h("div", { class: "opt" + (String(q.dap_an).toUpperCase() === L ? " right" : "") }, h("b", null, L), h("span", null, q[L])))),
      h("div", { class: "exp" }, h("b", null, "Đáp án " + String(q.dap_an).toUpperCase() + ". "), q.giai_thich),
      h("div", { class: "qfoot" }, lb ? h("span", { class: "chip " + (lb.nhan === "KHOP_NGUON" ? "ok" : "warn") }, lb.nhan === "KHOP_NGUON" ? "✓ Khớp nguồn" : "Nên xem lại") : null),
      h("div", { class: "qfoot" }, sourceBtn(q.segment_id)));
  }));
  const tgl = h("button", { class: "btn", onclick: () => { S.quiz.show = !S.quiz.show; list.classList.toggle("show", S.quiz.show); tgl.textContent = S.quiz.show ? "🙈 Ẩn đáp án" : "👁 Hiện đáp án"; } },
    S.quiz.show ? "🙈 Ẩn đáp án" : "👁 Hiện đáp án");
  return h("div", null, h("div", { class: "card" }, h("div", { class: "res-head", style: "border:0" }, h("h3", null, "📝 " + d.items.length + " câu trắc nghiệm"),
    h("span", { class: "chip ok" }, labels ? labels.filter((x) => x.nhan === "KHOP_NGUON").length + "/" + labels.length + " khớp nguồn" : "đã tự kiểm"),
    h("div", { class: "dl" }, tgl, dl("exam_pdf", "⬇ PDF đề thi", true), dl("answer_pdf", "⬇ PDF đáp án")))), list);
}

/* ---------- khởi động ---------- */
loadDocs().then(render);
