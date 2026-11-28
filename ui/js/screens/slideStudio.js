/* Screens 3–4 · Slides + narration + gate 2.
 *   build slides from the approved script (template) · estimate voice cost · voice job with progress
 *   per slide: canvas preview, audio track with A1..An markers, segments with label/source
 *   gate 2: edit a segment -> re-checked -> its audio invalidated -> "voice again" re-bills only it */
import { jobs, scripts, templates, voices } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { fmtCost, fmtNumber, mmss } from "../core/format.js";
import { go } from "../core/router.js";
import { prefs, setTrace, toast } from "../core/store.js";
import { audioTrack } from "../components/audioTrack.js";
import { slideCanvas } from "../components/slideCanvas.js";
import { sourcePanel } from "../components/sourcePanel.js";
import { badge, busy, button, card, empty, errorBox, pageHeader, progressBar, spinner, stepper } from "../components/ui.js";
import { SCRIPT_STEPS } from "./scriptNew.js";

const SPEEDS = [0.8, 0.9, 1, 1.1, 1.2];

export function mount(el, { params }) {
  const st = {
    sc: null, deck: null, templates: [], voices: [], provider: "", idx: 1,
    template: prefs.get("template", "template_1"), voice: prefs.get("voice", ""), speed: prefs.get("speed", 1),
    estimate: null, job: null, editing: null, staleVoice: false,
  };
  let alive = true;
  replace(el, spinner("Đang chuẩn bị slide…"));

  (async () => {
    try {
      st.sc = await scripts.get(params.id);
      if (st.sc.status !== "cho_duyet") return renderNotReady();
      const [tpl, vs] = await Promise.all([templates.list(), voices.list().catch(() => ({ provider: "?", voices: [] }))]);
      st.templates = tpl;
      st.voices = Array.isArray(vs.voices) ? vs.voices : [];
      st.provider = vs.provider;
      if (!st.templates.some((t) => t.id === st.template)) st.template = st.templates[0]?.id || "template_1";
      await rebuild();
    } catch (e) {
      replace(el, errorBox(e, () => mount(el, { params })));
    }
  })();

  function renderNotReady() {
    replace(el, stepper(SCRIPT_STEPS, 1), empty("Kịch bản chưa qua cổng 1. Quyết định hết các câu rồi gửi chờ duyệt trước khi tạo slide.",
      button("Về màn rà soát", { kind: "primary", onClick: () => go(`/scripts/${params.id}`) })));
  }

  async function rebuild() {
    st.deck = await scripts.buildSlides(st.sc.id, st.template);
    st.idx = Math.min(st.idx, st.deck.slides.length - 1);
    if (alive) render();
  }

  function scriptSlideOf(slide) {
    const i = slide?.eduguard?.scriptSlide;
    return i === undefined ? null : st.sc.slides.find((s) => s.index === i) || null;
  }

  function render() {
    const deck = st.deck;
    const slide = deck.slides[st.idx];
    const ss = scriptSlideOf(slide);
    const voicedSlides = st.sc.slides.filter((s) => s.audio?.url).length;
    replace(el,
      stepper(SCRIPT_STEPS, voicedSlides ? 3 : 2),
      pageHeader(`Slide & giọng đọc: ${st.sc.title}`, `${deck.slides.length} slide · template ${deck.template} · giọng: ${st.provider}`, [
        button("Về rà soát", { iconName: "arrowLeft", onClick: () => go(`/scripts/${st.sc.id}`) }),
      ]),
      settingsBar(),
      voiceBar(),
      h("div", { class: "studio" },
        h("nav", { class: "studio__thumbs", "aria-label": "Danh sách slide" }, deck.slides.map((s, i) => thumb(s, i))),
        h("div", { class: "studio__stage" },
          slideCanvas(slide, { width: deck.width, height: deck.height }),
          h("div", { class: "studio__nav" },
            button("Slide trước", { iconName: "arrowLeft", small: true, disabled: st.idx === 0, onClick: () => select(st.idx - 1) }),
            h("span", { class: "muted small" }, `Slide ${st.idx + 1} / ${deck.slides.length}`),
            button("Slide tiếp", { iconName: "arrowRight", small: true, disabled: st.idx >= deck.slides.length - 1, onClick: () => select(st.idx + 1) })),
          ss ? audioTrack(ss.audio, { onSegment: (id) => document.getElementById(`seg-${id}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }) }) : null,
          slide.remark ? h("details", { class: "remark" }, h("summary", null, "Ghi chú người nói (lời đọc)"), h("p", null, textOf(slide.remark))) : null),
        h("aside", { class: "studio__side" }, ss ? segmentsPanel(ss) : h("p", { class: "muted" },
          slide.eduguard?.kind === "cover" ? "Slide bìa — không có lời đọc cần kiểm." : "Slide kết — không có lời đọc cần kiểm."))));
  }

  function select(i) {
    st.idx = i;
    st.editing = null;
    render();
  }

  function thumb(s, i) {
    const ss = scriptSlideOf(s);
    const segs = ss?.doan || [];
    const bad = segs.filter((g) => g.nhan !== "KHOP_NGUON").length;
    const title = s.eduguard?.kind === "cover" ? "Bìa" : s.eduguard?.kind === "end" ? "Kết" : ss?.tieuDe || `Slide ${i + 1}`;
    return h("button", { class: `thumb${i === st.idx ? " is-active" : ""}`, type: "button", "aria-current": i === st.idx ? "true" : null,
      onClick: () => select(i) },
    h("span", { class: "thumb__n" }, String(i + 1)), h("span", { class: "thumb__title" }, title),
    h("span", { class: "thumb__meta" },
      ss ? (ss.audio?.url ? h("span", { title: "Đã có giọng đọc" }, icon("mic", 13)) : h("span", { class: "muted", title: "Chưa có giọng" }, "—")) : null,
      bad ? h("span", { class: "chip chip--warn" }, String(bad)) : null));
  }

  function settingsBar() {
    const tplSel = h("select", { class: "input input--sm", "aria-label": "Mẫu trình bày",
      onChange: async (e) => { st.template = e.target.value; prefs.set("template", st.template); await busy(null, rebuild); } },
    st.templates.map((t) => h("option", { value: t.id, selected: t.id === st.template }, t.title || t.id)));
    const voiceSel = h("select", { class: "input input--sm", "aria-label": "Giọng đọc",
      onChange: (e) => { st.voice = e.target.value; prefs.set("voice", st.voice); st.estimate = null; render(); } },
    h("option", { value: "" }, "Giọng mặc định"),
    st.voices.map((v) => {
      const id = typeof v === "string" ? v : v.id || v.name;
      const name = typeof v === "string" ? v : [v.name || v.id, v.gender, v.region || v.language].filter(Boolean).join(" · ");
      return h("option", { value: id, selected: id === st.voice }, name);
    }));
    const speedSel = h("select", { class: "input input--sm", "aria-label": "Tốc độ đọc",
      onChange: (e) => { st.speed = Number(e.target.value); prefs.set("speed", st.speed); st.estimate = null; render(); } },
    SPEEDS.map((s) => h("option", { value: s, selected: s === st.speed }, `${s}×`)));
    return h("div", { class: "toolbar" },
      h("label", { class: "inline-field" }, "Mẫu", tplSel),
      h("label", { class: "inline-field" }, "Giọng", voiceSel),
      h("label", { class: "inline-field" }, "Tốc độ", speedSel));
  }

  function voiceBar() {
    if (st.job) {
      return card(null, h("div", { class: "row row--between" }, h("strong", null, "Đang sinh giọng đọc"),
        button("Huỷ", { small: true, onClick: () => jobs.cancel(st.job.id) })),
      progressBar(st.job.progress_pct || 0, st.job.message || st.job.status));
    }
    const est = st.estimate;
    const estimateBtn = button("Ước tính trước", { iconName: "info", small: true,
      onClick: async (e) => {
        const r = await busy(e.currentTarget, () => scripts.voiceEstimate(st.sc.id, st.voice || null, st.speed));
        if (r) { st.estimate = r; render(); }
      } });
    const voiceBtn = button(st.sc.slides.some((s) => s.audio?.url) ? "Sinh lại giọng (chỉ đoạn đã đổi)" : "Sinh giọng đọc", {
      kind: "primary", iconName: "mic", onClick: startVoice });
    return card(null,
      h("div", { class: "row row--between row--wrap" },
        h("div", null, h("strong", null, "Giọng thuyết trình"),
          h("p", { class: "muted small" }, "Mỗi đoạn A1..An là một clip riêng; sửa một đoạn chỉ sinh lại đoạn đó.")),
        h("div", { class: "row" }, estimateBtn, voiceBtn)),
      st.staleVoice ? h("div", { class: "alert alert--warn small" }, "Có đoạn vừa sửa ở cổng 2: giọng của slide đó cần sinh lại.") : null,
      est ? h("div", { class: "stats stats--sm" },
        miniStat("Đoạn", fmtNumber(est.segments)), miniStat("Ký tự tính phí", `${fmtNumber(est.billableChars)} / ${fmtNumber(est.chars)}`),
        miniStat("Đã có sẵn (cache)", fmtNumber(est.cachedSegments)), miniStat("Request", fmtNumber(est.requests)),
        miniStat("Thời lượng ~", mmss(est.audioSeconds)), miniStat("Chi phí ước tính", fmtCost(est.estimatedCost, est.currency)),
        est.quota?.limit ? miniStat("Hạn mức tháng", `${fmtNumber(est.quota.used)} / ${fmtNumber(est.quota.limit)}`) : null) : null);
  }

  async function startVoice(e) {
    const started = await busy(e.currentTarget, () => scripts.startVoice(st.sc.id, st.voice || null, st.speed));
    if (!started) return;
    st.job = { id: started.jobId, status: "pending", progress_pct: 0 };
    render();
    try {
      const snap = await jobs.wait(started.jobId, (s) => { st.job = s; if (alive) render(); });
      st.job = null;
      if (snap.status !== "done") throw new Error(snap.error || `Job ${snap.status}`);
      const r = snap.result;
      toast(`Đã sinh giọng: ${fmtNumber(r.billedChars)} ký tự tính phí · ${mmss(r.totalDuration)} · ${fmtCost(r.cost, r.currency)}`, "ok", 7000);
      if (r.quotaWarning) toast(r.quotaWarning, "warn", 8000);
      st.sc = await scripts.get(st.sc.id);
      st.staleVoice = false;
      st.estimate = null;
      await rebuild();
    } catch (err) {
      st.job = null;
      toast(err.message, "bad", 9000);
      if (alive) render();
    }
  }

  function segmentsPanel(ss) {
    return h("div", { class: "stack" },
      h("h2", { class: "card__title" }, `Lời đọc · slide ${ss.index + 1}`),
      ss.doan.length ? null : h("p", { class: "muted" }, "Không có đoạn nào được chấp nhận ở slide này."),
      ss.doan.map((g) => segmentCard(ss, g)));
  }

  function segmentCard(ss, g) {
    const isEditing = st.editing === `${ss.index}:${g.id}`;
    const ta = h("textarea", { class: "input textarea", rows: 4, value: g.text, "aria-label": `Sửa đoạn ${g.id}` });
    const revise = (text) => async (e) => {
      const res = await busy(e.currentTarget, () => scripts.revise(st.sc.id, ss.index, g.id, text));
      if (!res) return;
      setTrace(`Cổng 2 · kiểm lại đoạn ${g.id} slide ${ss.index + 1}`, res.trace);
      st.sc = res.data;
      st.editing = null;
      st.staleVoice = true;
      const updated = res.data.slides[ss.index].doan.find((x) => x.id === g.id);
      toast(updated?.nhan === "KHOP_NGUON" ? "Đoạn đã sửa khớp nguồn" : `Đoạn đã sửa: ${updated?.nhan}`, updated?.nhan === "KHOP_NGUON" ? "ok" : "warn");
      await rebuild();
    };
    return h("article", { class: `seg seg--${g.nhan}`, id: `seg-${g.id}` },
      h("div", { class: "row row--between" }, h("span", { class: "mono" }, g.id),
        h("span", { class: "row" }, badge(g.nhan, { short: true }),
          g.voice ? h("span", { class: "muted small mono" }, `${mmss(g.voice.start)}–${mmss(g.voice.end)}`) : null)),
      isEditing
        ? h("div", { class: "stack" }, ta, h("div", { class: "row" },
          button("Lưu & kiểm lại", { kind: "primary", small: true, onClick: (e) => ta.value.trim() && revise(ta.value.trim())(e) }),
          button("Huỷ", { small: true, onClick: () => { st.editing = null; render(); } })))
        : h("p", null, g.text),
      g.lyDo && g.nhan !== "KHOP_NGUON" ? h("p", { class: "muted small" }, g.lyDo) : null,
      g.deXuatSua ? h("div", { class: "detail__block detail__block--fix" }, h("p", null, g.deXuatSua),
        button("Dùng đề xuất", { small: true, onClick: revise(g.deXuatSua) })) : null,
      h("details", null, h("summary", null, "Đoạn nguồn"), sourcePanel(g.nguon, g.text, { title: g.segmentId || "Nguồn" })),
      isEditing ? null : h("div", { class: "row" }, button("Sửa (cổng 2)", { small: true, iconName: "edit",
        onClick: () => { st.editing = `${ss.index}:${g.id}`; render(); } })));
  }

  return () => { alive = false; };
}

function miniStat(label, value) {
  return h("div", { class: "stat stat--sm" }, h("div", { class: "stat__value" }, value), h("div", { class: "stat__label" }, label));
}

function textOf(html) {
  const d = new DOMParser().parseFromString(String(html || ""), "text/html");
  return (d.body.textContent || "").trim();
}
