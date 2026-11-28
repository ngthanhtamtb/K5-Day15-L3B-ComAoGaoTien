/* Document — the hub. One primary action (create a lesson), quiz as secondary; the create form
 * opens in place (no separate page, no document picker). What the parser read is folded away. */
import { documents, jobs, quizzes, scripts } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { go, href } from "../core/router.js";
import { prefs, setTrace, toast } from "../core/store.js";
import { busy, button, disclosure, errorState, linkButton, pageHead, progress, skeleton } from "../components/ui.js";

const SAMPLE = `Slide 1: Nền tảng LLM
LLM sinh văn bản theo vòng lặp tự hồi quy, mỗi bước dự đoán một token kế tiếp.
Tăng temperature giúp câu trả lời của model tập trung và ổn định hơn.`;

export function mount(el, { params, query, shell }) {
  const st = { doc: null, scs: [], qzs: [], create: query.create || null, pasteMode: false, job: null };
  replace(el, skeleton(5, 40));
  load();

  async function load() {
    try {
      const [doc, scs, qzs] = await Promise.all([documents.get(params.docId, false), scripts.list(), quizzes.list()]);
      st.doc = doc;
      st.scs = scs.filter((s) => s.docId === doc.doc_id);
      st.qzs = qzs.filter((q) => q.docId === doc.doc_id);
      shell.setCrumbs([{ label: doc.filename }]);
      render();
    } catch (e) {
      replace(el, errorState(e, load));
    }
  }

  function render() {
    const d = st.doc;
    const images = Object.values(d.images || {});
    const tables = Object.values(d.tables || {});
    const pages = d.meta?.pages ?? d.meta?.slides;
    const stats = [pages ? `${pages} trang` : null, `${d.chunks.length} đoạn nguồn`, images.length ? `${images.length} hình` : null,
      tables.length ? `${tables.length} bảng` : null].filter(Boolean).join(" · ");
    replace(el,
      pageHead({ eyebrow: "Tài liệu gốc", title: d.filename, subtitle: stats, actions: [
        button("Tạo quiz", { iconName: "quiz", onClick: () => open("quiz") }),
        // while a create form is open, its submit button is the screen's only primary action
        button("Tạo bài giảng", { kind: st.create ? "secondary" : "primary", iconName: "slides", onClick: () => open("lesson"), disabled: Boolean(st.job) }),
      ] }),
      st.create === "lesson" ? lessonForm() : st.create === "quiz" ? quizForm() : null,
      work(),
      disclosure(`Nội dung đã đọc từ tài liệu`, contentTabs(d, images, tables)),
      d.meta?.scan_pages_without_ocr?.length ? h("p", { class: "small muted" },
        `${d.meta.scan_pages_without_ocr.length} trang là bản scan chưa OCR — nội dung các trang này chỉ có dạng hình.`) : null);
  }

  function open(kind) {
    st.create = st.create === kind ? null : kind;
    render();
    el.querySelector(".create textarea, .create input")?.focus();
  }

  function work() {
    if (!st.scs.length && !st.qzs.length) return null;
    return h("section", { class: "stack stack--sm" }, h("h2", null, "Đã tạo từ tài liệu này"),
      h("div", { class: "docrow__work" },
        st.scs.map((s) => h("a", { class: "work", href: href(`/scripts/${s.id}`) }, icon("script", 15), s.title,
          s.needsReview ? h("span", { class: "tag tag--warn" }, `${s.needsReview} cần xem`) : h("span", { class: "tag tag--ok" }, "ổn"))),
        st.qzs.map((q) => h("a", { class: "work", href: href(`/quizzes/${q.id}`) }, icon("quiz", 15), q.title,
          q.needsReview ? h("span", { class: "tag tag--warn" }, `${q.needsReview} cần xem`) : h("span", { class: "tag tag--ok" }, "ổn")))));
  }

  /* ---------- create lesson: AI proposes the script from the document (default); pasting is secondary ---------- */
  function lessonForm() {
    if (st.job) return jobCard();
    return st.pasteMode ? pasteForm() : proposeForm();
  }

  function proposeForm() {
    const saved = prefs.get("deck", { n: 6, narrate: true, khung: "bai_giang" });
    const n = h("input", { class: "input input--num", id: "dn", type: "number", min: 1, max: 30, value: saved.n });
    const topic = h("input", { class: "input", id: "dtopic", placeholder: "Để trống = toàn bộ tài liệu" });
    const title = h("input", { class: "input", id: "dtitle", placeholder: "Tự đặt theo nội dung nếu để trống" });
    const narrate = h("input", { type: "checkbox", id: "dvoice", checked: saved.narrate });
    const khung = h("select", { class: "input", id: "dkhung" },
      [["bai_giang", "Bài giảng đầy đủ: nội dung chính → bài → tóm tắt → câu hỏi nhanh"], ["gon", "Chỉ slide nội dung"]]
        .map(([v, l]) => h("option", { value: v, selected: (saved.khung || "bai_giang") === v }, l)));
    const go_ = button("Đề xuất kịch bản & tạo slide", { kind: "primary", type: "submit" });
    const d = st.doc;
    const media = [Object.keys(d.images || {}).length ? `${Object.keys(d.images).length} hình` : null,
      Object.keys(d.tables || {}).length ? `${Object.keys(d.tables).length} bảng` : null].filter(Boolean).join(" và ");

    return h("form", { class: "card create", onSubmit: async (e) => {
      e.preventDefault();
      const body = { soSlide: Number(n.value) || 6, chuDe: topic.value.trim() || null, title: title.value.trim() || null,
        narrate: narrate.checked, khung: khung.value };
      prefs.set("deck", { n: body.soSlide, narrate: body.narrate, khung: body.khung });
      const started = await busy(go_, () => documents.deck(d.doc_id, body));
      if (!started) return;
      st.job = { id: started.jobId, progress_pct: 0, message: "Đang bắt đầu" };
      render();
      try {
        const snap = await jobs.wait(started.jobId, (x) => { st.job = x; render(); });
        st.job = null;
        if (snap.status !== "done") throw new Error(snap.error || "Không tạo được slide");
        const r = snap.result;
        setTrace(`Đề xuất kịch bản “${r.title}” và kiểm nguồn`, r.trace);
        if (r.voiceError) toast(r.voiceError, "bad", 10000);
        go(`/scripts/${r.scriptId}/slides`);
      } catch (err) {
        st.job = null;
        toast(err.message, "bad", 9000);
        render();
      }
    } },
    h("h2", null, "Bài giảng mới"),
    h("p", { class: "small muted" }, `AI đề xuất kịch bản thuyết trình chỉ từ tài liệu này${media ? `, đưa ${media} của tài liệu lên slide` : ""}, `,
      "chọn khung cho từng slide (hình, bảng, so sánh, quy trình…), kiểm từng câu với nguồn rồi tạo slide HTML có giọng đọc. ",
      "Bạn chỉ cần xem những câu được đánh dấu."),
    h("div", { class: "row row--wrap", style: { gap: "24px", alignItems: "flex-end" } },
      field("Số slide", n),
      h("label", { class: "switch", for: "dvoice" }, narrate, h("span", null, h("strong", null, "Tạo giọng đọc"),
        h("span", { class: "field__help", style: { display: "block" } }, "Có thể tạo sau trong màn slide.")))),
    disclosure("Tuỳ chọn", h("div", { class: "stack stack--sm" }, field("Khung bài", khung), field("Chủ đề trong tài liệu", topic),
      field("Tên bài giảng", title)), { flat: true }),
    h("div", { class: "create__foot" },
      linkButton("Đã có kịch bản? Dán vào để kiểm", () => { st.pasteMode = true; render(); }),
      h("div", { class: "row" }, button("Huỷ", { kind: "ghost", onClick: () => { st.create = null; render(); } }), go_)));
  }

  function jobCard() {
    return h("div", { class: "card create", "aria-live": "polite" }, h("h2", null, "Đang tạo bài giảng"),
      progress(st.job.progress_pct || 0, st.job.message || "Đang xử lý"),
      h("p", { class: "small muted" }, "Đề xuất kịch bản → kiểm từng câu với tài liệu → gắn hình, bảng → giọng đọc → slide HTML. Có thể mất 1–3 phút."),
      h("div", null, button("Huỷ", { kind: "ghost", small: true, onClick: () => jobs.cancel(st.job.id) })));
  }

  function pasteForm() {
    const text = h("textarea", { class: "input", id: "draft", rows: 10, placeholder: "Slide 1: Tiêu đề\nMỗi câu là một đoạn lời đọc…" });
    const go_ = button("Kiểm tra kịch bản", { kind: "primary", type: "submit" });
    return h("form", { class: "card create", onSubmit: async (e) => {
      e.preventDefault();
      if (!text.value.trim()) return text.focus();
      const res = await busy(go_, () => scripts.create({ docId: st.doc.doc_id, noiDung: text.value }));
      if (!res) return;
      setTrace(`Kiểm tra kịch bản “${res.data.title}”`, res.trace);
      go(`/scripts/${res.data.id}`);
    } },
    h("h2", null, "Dán kịch bản có sẵn"),
    field("Kịch bản", text, "Bắt đầu mỗi slide bằng “Slide N: tiêu đề”. Mỗi câu là một đoạn lời đọc và sẽ được kiểm với tài liệu."),
    h("div", { class: "create__foot" },
      h("div", { class: "row row--wrap" }, linkButton("Để AI đề xuất kịch bản", () => { st.pasteMode = false; render(); }),
        h("span", { class: "muted" }, "·"), linkButton("Dùng ví dụ", () => { text.value = SAMPLE; text.focus(); })),
      h("div", { class: "row" }, button("Huỷ", { kind: "ghost", onClick: () => { st.create = null; render(); } }), go_)));
  }

  /* ---------- create quiz: count + depth; the rest is advanced ---------- */
  function quizForm() {
    const saved = prefs.get("quiz", { n: 10, types: ["mcq"], bloom: [40, 30, 20, 10], depth: true });
    const n = h("input", { class: "input input--num", id: "qn", type: "number", min: 1, max: 60, value: saved.n });
    const depth = h("input", { type: "checkbox", id: "qdepth", checked: saved.depth });
    const title = h("input", { class: "input", id: "qtitle", placeholder: "Tự đặt theo tài liệu nếu để trống" });
    const types = [["mcq", "Trắc nghiệm 4 lựa chọn"], ["true_false", "Đúng / Sai"], ["short_answer", "Trả lời ngắn"]].map(([v, l]) =>
      h("label", { class: "switch" }, h("input", { type: "checkbox", value: v, checked: saved.types.includes(v) }), l));
    const bloomNames = ["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"];
    const bloom = bloomNames.map((b, i) => h("label", { class: "field" }, h("span", { class: "field__label" }, `${b} (%)`),
      h("input", { class: "input input--num", type: "number", min: 0, max: 100, value: saved.bloom[i] })));
    const go_ = button("Sinh quiz", { kind: "primary", type: "submit" });

    return h("form", { class: "card create", onSubmit: async (e) => {
      e.preventDefault();
      const picked = types.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
      const mix = Object.fromEntries(bloomNames.map((b, i) => [b, Number(bloom[i].querySelector("input").value) || 0]));
      const body = { numQuestions: Number(n.value), questionTypes: picked.length ? picked : ["mcq"], bloomMix: mix,
        depth: depth.checked, verify: true, title: title.value.trim() || null };
      prefs.set("quiz", { n: body.numQuestions, types: body.questionTypes, bloom: Object.values(mix), depth: depth.checked });
      const res = await busy(go_, () => quizzes.generate(st.doc.doc_id, body));
      if (!res) return;
      setTrace(`Sinh quiz “${res.title}” và kiểm từng phương án`, res.trace);
      go(`/quizzes/${res.id}`);
    } },
    h("h2", null, "Quiz mới"),
    h("div", { class: "row row--wrap", style: { gap: "24px", alignItems: "flex-end" } },
      field("Số câu", n),
      h("label", { class: "switch", for: "qdepth" }, depth, h("span", null, h("strong", null, "Câu hỏi có chiều sâu"),
        h("span", { class: "field__help", style: { display: "block" } }, "Tình huống, nhiều bước, đọc bảng/hình; phương án nhiễu nhắm vào lỗi hiểu sai.")))),
    disclosure("Tuỳ chọn nâng cao", h("div", { class: "stack" }, field("Tên bộ quiz", title),
      h("fieldset", { class: "stack stack--sm", style: { border: 0, padding: 0, margin: 0 } }, h("legend", { class: "field__label" }, "Loại câu"), h("div", { class: "choices" }, types)),
      h("fieldset", { class: "stack stack--sm", style: { border: 0, padding: 0, margin: 0 } }, h("legend", { class: "field__label" }, "Mức độ Bloom"), h("div", { class: "choices" }, bloom))), { flat: true }),
    h("div", { class: "create__foot" }, h("span", { class: "small muted" }, "Mỗi câu được kiểm cả 4 phương án với tài liệu · 20–60 giây."),
      h("div", { class: "row" }, button("Huỷ", { kind: "ghost", onClick: () => { st.create = null; render(); } }), go_)));
  }
}

function field(label, control, help) {
  const helpId = help && control.id ? `${control.id}-help` : null;
  if (helpId) control.setAttribute("aria-describedby", helpId);
  return h("label", { class: "field", for: control.id || null }, h("span", { class: "field__label" }, label), control,
    help ? h("span", { class: "field__help", id: helpId }, help) : null);
}

function contentTabs(d, images, tables) {
  let tab = "chunks";
  const body = h("div", { class: "stack" });
  const tabs = h("div", { class: "tabs", role: "tablist" });
  const draw = () => {
    replace(tabs, [["chunks", `Đoạn nguồn (${d.chunks.length})`], ["images", `Hình (${images.length})`], ["tables", `Bảng (${tables.length})`]].map(([k, l]) =>
      h("button", { class: "tab", role: "tab", type: "button", "aria-selected": String(tab === k), onClick: () => { tab = k; draw(); } }, l)));
    replace(body, tab === "chunks" ? d.chunks.map((c) => h("div", { class: "stack stack--sm" },
      h("div", { class: "row row--between small muted" }, h("code", null, c.id), h("span", null, (c.heading_path || []).join(" › "))),
      h("p", { class: "prewrap" }, c.text)))
      : tab === "images" ? (images.length ? h("div", { class: "gallery" }, images.map((img) => h("figure", null,
        h("img", { src: img.url, alt: img.alt || img.caption || img.id, loading: "lazy" }),
        h("figcaption", null, [img.id, img.page ? `trang ${img.page}` : null, img.alt].filter(Boolean).join(" · "))))) : h("p", { class: "muted" }, "Không có hình."))
        : (tables.length ? tables.map((t) => {
          const rows = [];
          for (const c of t.cells) (rows[c.row] ||= [])[c.col] = c.text;
          return h("div", { class: "table-wrap" }, h("table", { class: "data" }, h("caption", { class: "small muted", style: { textAlign: "left" } }, t.id),
            h("tbody", null, rows.map((r, i) => h("tr", null, (r || []).map((cell) => h(i === 0 ? "th" : "td", null, cell ?? "")))))));
        }) : h("p", { class: "muted" }, "Không có bảng.")));
  };
  draw();
  return h("div", { class: "stack" }, tabs, body);
}
