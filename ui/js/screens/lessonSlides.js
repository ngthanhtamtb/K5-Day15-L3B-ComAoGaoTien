/* Slides tab — the real HTML deck (document figures/tables + narration) previewed in a sandboxed
 * iframe. One primary action: create / update narration, or open the deck once it is complete.
 * Below: narration per slide (folded), editable in place; edits re-render the deck. */
import { jobs, scripts, voices } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { fmtCost, fmtNumber, mmss } from "../core/format.js";
import { prefs, toast } from "../core/store.js";
import { claimLine } from "../components/claimCard.js";
import { busy, button, disclosure, errorState, notice, progress, skeleton } from "../components/ui.js";

const SPEEDS = [0.8, 0.9, 1, 1.1, 1.2];
/* slide frames (backend app/edu/slide_frame.py) */
const FRAME_NAMES = { agenda: "Nội dung chính", bullets: "Ý chính", image_text: "Hình + ý", table: "Bảng",
  comparison: "So sánh", process: "Quy trình", key_fact: "Khái niệm / con số", summary: "Tóm tắt", check: "Câu hỏi nhanh" };
const included = (g) => g.quyetDinh !== "tu_choi_cau" && g.nhan !== "TU_CHOI";

export function slidesView(el, ctx) {
  const st = (ctx.slides ||= { url: null, builtFor: null, idx: 0, job: null, estimate: null, estFor: null,
    voice: prefs.get("voice", ""), speed: prefs.get("speed", 1), voices: null, provider: "", voiceError: null });
  let alive = true;
  let frame = null;
  const stamp = () => `${ctx.sc.updatedAt}`;

  (async () => {
    if (st.builtFor !== stamp() || !st.url) {
      replace(el, skeleton(1, 420));
      try {
        st.url = (await scripts.html(ctx.sc.id)).htmlUrl;
        st.builtFor = stamp();
      } catch (e) {
        return replace(el, errorState(e, () => slidesView(el, ctx)));
      }
    }
    if (alive) render();
    const estKey = `${stamp()}|${st.voice}|${st.speed}`;
    if (st.estFor !== estKey && !st.job) {
      scripts.voiceEstimate(ctx.sc.id, st.voice || null, st.speed)
        .then((est) => { st.estimate = est; st.estFor = estKey; if (alive) render(); }).catch(() => {});
    }
  })();

  /* deck numbering: 1 = cover, then every slide that still has content, then the closing slide */
  function deckSlides() {
    return ctx.sc.slides.filter((s) => s.doan.some(included) || s.yChinh?.length);
  }

  /* The iframe is created once per deck version and never re-parented: moving or re-creating it
   * would reload the deck (and stop its audio) every time the bar or the list re-renders. */
  const barSlot = h("div");
  const listSlot = h("section", { class: "stack stack--sm" });
  let frameFor = null;

  function render() {
    const shown = deckSlides();
    if (!shown.length) { frameFor = null; return replace(el, notice("Mọi câu đã bị bỏ — không còn gì để dựng slide.")); }
    if (frameFor !== stamp() || !frame || !frame.isConnected) {
      frame = h("iframe", { class: "deck-frame", title: `Slide: ${ctx.sc.title}`, sandbox: "allow-scripts",
        src: `${st.url}?v=${encodeURIComponent(stamp())}#${st.idx + 1}`, allow: "fullscreen" });
      frameFor = stamp();
      replace(el, barSlot, frame,
        h("p", { class: "small muted" }, "Trong khung slide: ← → để chuyển, P phát giọng, N ghi chú người nói, F toàn màn hình."),
        listSlot);
    }
    replace(barSlot, voiceBar());
    replace(listSlot, h("h2", null, "Lời đọc theo slide"), shown.map((s, k) => slideBlock(s, k + 1)));
  }

  function jump(deckIndex) {
    st.idx = deckIndex;
    if (frame) frame.src = `${st.url}?v=${encodeURIComponent(stamp())}#${deckIndex + 1}`;
  }

  function slideBlock(s, deckIndex) {
    const segs = s.doan.filter(included);
    const flagged = segs.filter((g) => (g.nhan === "SAI_NGUON" || g.nhan === "THIEU_NGUON") && g.quyetDinh !== "chap_nhan").length;
    const summary = h("span", { class: "row row--wrap" }, h("span", null, `${deckIndex + 1}. ${s.tieuDe}`),
      FRAME_NAMES[s.layout] ? h("span", { class: "pill" }, FRAME_NAMES[s.layout]) : null,
      s.imageIds?.length ? h("span", { class: "pill" }, icon("image", 13), "hình") : null,
      s.tableIds?.length ? h("span", { class: "pill" }, icon("table", 13), "bảng") : null,
      flagged ? h("span", { class: "tag tag--warn" }, `${flagged} cần xem`) : null,
      h("span", { class: "small muted" }, s.audio?.url ? mmss(s.audio.duration) : "chưa có giọng"));
    return disclosure(summary, h("div", null,
      segs.map((g) => claimLine({ seg: g, showTag: g.nhan !== "KHOP_NGUON" && g.nhan !== "DAN_DAT", where: { key: `${s.index}-${g.id}`, short: g.id },
        act: (action, extra) => ctx.act(s.index, g, action, extra) }))),
    { onToggle: (open) => open && jump(deckIndex) });
  }

  function voiceBar() {
    if (st.job) {
      return h("div", { class: "voicebar" }, h("div", { style: { flex: 1, minWidth: "240px" } },
        progress(st.job.progress_pct || 0, st.job.message || "Đang sinh giọng đọc")),
      button("Huỷ", { kind: "ghost", small: true, onClick: () => jobs.cancel(st.job.id) }));
    }
    const all = ctx.sc.slides.flatMap((s) => s.doan.filter(included));
    const missing = all.filter((g) => !g.voice).length;
    const hasAny = all.some((g) => g.voice);
    const done = hasAny && !missing;
    const est = st.estimate;
    const estText = est ? [`≈ ${mmss(est.audioSeconds)}`, `${fmtNumber(est.billableChars)} ký tự tính phí`,
      est.estimatedCost === null ? "chưa cấu hình giá" : fmtCost(est.estimatedCost, est.currency)].join(" · ") : "Đang ước tính…";
    const total = ctx.sc.slides.reduce((t, s) => t + (s.audio?.duration || 0), 0);
    return h("div", { class: "voicebar" },
      h("div", { class: "voicebar__info" },
        h("strong", null, done ? "Slide đã có giọng đọc" : hasAny ? `${missing} câu chưa có giọng` : "Slide chưa có giọng đọc"),
        h("span", { class: "small muted" }, done ? `Tổng ${mmss(total)}` : estText)),
      h("div", { class: "row row--wrap" }, options(),
        done ? null : button(hasAny ? "Cập nhật giọng đọc" : "Tạo giọng đọc", { kind: "primary", iconName: "mic", onClick: startVoice }),
        // exactly one primary: opening the deck becomes primary once narration is complete
        h("a", { class: done ? "btn btn--primary" : "btn", href: st.url, target: "_blank", rel: "noopener" }, icon("slides", 18), "Mở slide HTML")));
  }

  function options() {
    const body = h("div", { class: "stack stack--sm", style: { minWidth: "240px" } });
    return disclosure("Giọng & tốc độ", body, { flat: true, onToggle: async (open) => {
      if (!open) return;
      if (!st.voices) {
        replace(body, skeleton(2, 36));
        const v = await voices.list().catch((e) => ({ voices: [], error: e.message }));
        st.voices = Array.isArray(v.voices) ? v.voices : [];
        st.provider = v.provider || "";
        st.voiceError = v.error || null;
      }
      const sel = (label, value, items, onChange) => h("label", { class: "field" }, h("span", { class: "field__label" }, label),
        h("select", { class: "input", onChange: (e) => onChange(e.target.value) },
          items.map(([v, l]) => h("option", { value: v, selected: String(v) === String(value) }, l))));
      replace(body,
        st.voiceError ? h("p", { class: "small", style: { color: "var(--bad)" } }, `Không lấy được danh sách giọng: ${st.voiceError}`) : null,
        sel(`Giọng${st.provider ? ` (${st.provider})` : ""}`, st.voice, [["", "Mặc định của dịch vụ"], ...st.voices.map((v) => {
          const id = typeof v === "string" ? v : v.id || v.name;
          return [id, typeof v === "string" ? v : [v.name || v.id, v.gender, v.region || v.language].filter(Boolean).join(" · ")];
        })], (v) => { st.voice = v; prefs.set("voice", v); st.estFor = null; alive = false; slidesView(el, ctx); }),
        sel("Tốc độ", st.speed, SPEEDS.map((s) => [s, `${s}×`]), (v) => { st.speed = Number(v); prefs.set("speed", st.speed); st.estFor = null; alive = false; slidesView(el, ctx); }));
    } });
  }

  async function startVoice(e) {
    const started = await busy(e.currentTarget, () => scripts.startVoice(ctx.sc.id, st.voice || null, st.speed));
    if (!started) return;
    st.job = { id: started.jobId, progress_pct: 0 };
    render();
    try {
      const snap = await jobs.wait(started.jobId, (s) => { st.job = s; if (alive) render(); });
      st.job = null;
      if (snap.status !== "done") throw new Error(snap.error || "Không sinh được giọng đọc");
      const r = snap.result;
      toast(`Đã có giọng đọc · ${mmss(r.totalDuration)} · ${fmtNumber(r.billedChars)} ký tự tính phí`, "ok");
      st.builtFor = null;
      ctx.set(await scripts.get(ctx.sc.id));
    } catch (err) {
      st.job = null;
      toast(err.message, "bad", 10000);
      if (alive) render();
    }
  }

  return { destroy() { alive = false; } };
}
