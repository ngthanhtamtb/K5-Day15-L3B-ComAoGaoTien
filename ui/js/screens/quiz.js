/* Quiz — same model as the lesson script: only questions that need a look are open.
 * Every question except dropped ones goes into the PDF; there is no approval step. */
import { quizzes } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { setTrace, toast } from "../core/store.js";
import { sourcePanel } from "../components/sourcePanel.js";
import { busy, button, disclosure, errorState, healthBar, pageHead, skeleton, tag } from "../components/ui.js";

const DEPTH = { tinh_huong: "Tình huống", nhieu_buoc: "Nhiều bước", doc_bang: "Đọc bảng", doc_hinh: "Đọc hình" };
const TONE = { KHOP_NGUON: "ok", SAI_NGUON: "bad", THIEU_NGUON: "warn" };

export function mount(el, { params, shell }) {
  const st = { qs: null, editing: null };
  let alive = true;
  replace(el, skeleton(6, 28));
  load();

  async function load() {
    try {
      st.qs = await quizzes.get(params.id);
      if (alive) render();
    } catch (e) {
      replace(el, errorState(e, load));
    }
  }

  const openFix = (q) => (q.fixes || []).filter((f) => !f.fixed && f.severity === "error");
  function classify() {
    const need = [], fine = [], dropped = [];
    for (const q of st.qs.questions) {
      const bad = ["SAI_NGUON", "THIEU_NGUON"].includes(q.verdict?.nhan) || openFix(q).length;
      if (q.decision === "tu_choi_cau") dropped.push(q);
      else if (bad && q.decision !== "chap_nhan") need.push(q);
      else fine.push(q);
    }
    return { need, fine, dropped };
  }

  function setQuestion(q) {
    st.qs.questions = st.qs.questions.map((x) => (x.id === q.id ? q : x));
    render();
  }

  function render() {
    const qs = st.qs;
    shell.setCrumbs([{ label: "Tài liệu", path: `/documents/${qs.docId}` }, { label: qs.title }]);
    const { need, fine, dropped } = classify();
    const counts = {};
    for (const q of qs.questions) if (q.decision !== "tu_choi_cau" && q.verdict?.nhan) counts[q.verdict.nhan] = (counts[q.verdict.nhan] || 0) + 1;
    const printed = qs.questions.length - dropped.length;

    replace(el,
      pageHead({ eyebrow: "Quiz", title: qs.title, subtitle: `${printed} câu sẽ có trong đề`, actions: [
        h("a", { class: "btn", href: quizzes.pdfUrl(qs.id, true), target: "_blank", rel: "noopener" }, icon("download", 18), "Đáp án"),
        h("a", { class: "btn btn--primary", href: quizzes.pdfUrl(qs.id, false), target: "_blank", rel: "noopener" }, icon("download", 18), "Tải đề PDF"),
      ] }),
      h("div", { class: "work-grid" },
        h("div", { class: "stack" },
          need.length
            ? h("section", { class: "stack" },
              h("div", { class: "section-title" }, h("h2", null, "Cần xem"), h("span", { class: "count" }, String(need.length))),
              h("p", { class: "small muted" }, "Đáp án sai, có hơn một đáp án đúng, hoặc không tìm thấy căn cứ trong tài liệu."),
              need.map((q) => card(q, true)))
            : h("div", { class: "done-state" }, icon("check", 28), h("div", null, h("strong", null, "Không còn câu nào cần xem"),
              h("p", { class: "small muted" }, "Đề đã sẵn sàng để tải."))),
          fine.length ? disclosure(h("span", { class: "row" }, "Ổn", h("span", { class: "count" }, String(fine.length))),
            fine.map((q) => card(q, false))) : null,
          dropped.length ? disclosure(h("span", { class: "row" }, "Đã bỏ khỏi đề", h("span", { class: "count" }, String(dropped.length))),
            dropped.map((q) => h("div", { class: "line" }, h("span", { class: "line__id" }, `${q.number}`), h("p", null, h("s", null, q.stem)),
              button("Khôi phục", { kind: "ghost", small: true, iconName: "undo", onClick: (e) => decide(e, q, "reset") })))) : null),
        h("aside", { class: "work-grid__side" }, h("div", { class: "card" }, h("h2", null, "Kiểm từng phương án"),
          Object.keys(counts).length ? healthBar(counts, ["KHOP_NGUON", "SAI_NGUON", "THIEU_NGUON"]) : h("p", { class: "small muted" }, "Chưa có kết quả kiểm."),
          button("Kiểm định sâu", { iconName: "shield", title: "Thêm kiểm tra lộ đáp án, phương án trùng, câu mơ hồ",
            onClick: async (e) => {
              const r = await busy(e.currentTarget, () => quizzes.evaluate(qs.id, true), { ok: "Đã kiểm định — câu có vấn đề nằm trong “Cần xem”" });
              if (r) { st.qs = r; render(); }
            } }),
          h("p", { class: "small muted" }, "Đề PDF gồm mọi câu chưa bị bỏ, kèm bản đáp án có giải thích và nguồn.")))));
  }

  function card(q, expanded) {
    const v = q.verdict;
    const tone = q.decision === "chap_nhan" ? "ok" : TONE[v?.nhan] || "refuse";
    const meta = [`Câu ${q.number}`, q.bloom, DEPTH[q.depth]].filter(Boolean).join(" · ");
    const editing = st.editing === q.id;
    const details = h("div", { class: "stack stack--sm" },
      options(q),
      q.explanation ? disclosure("Giải thích", h("p", null, q.explanation), { flat: true }) : null,
      v?.nguon ? disclosure("Xem đoạn nguồn", sourcePanel(v.nguon, q.stem), { flat: true }) : null);
    return h("article", { class: `issue issue--${tone}` },
      h("div", { class: "issue__meta" }, h("span", null, meta),
        q.decision === "chap_nhan" ? h("span", { class: "tag tag--ok" }, "Bạn đã giữ") : v ? tag(v.nhan) : h("span", { class: "tag" }, "Chưa kiểm")),
      editing ? editForm(q) : h("p", { class: "issue__text" }, q.stem),
      editing ? null : expanded ? details : disclosure("Phương án & giải thích", details, { flat: true }),
      !editing && expanded && v?.lyDo ? h("p", { class: "issue__reason" }, v.lyDo) : null,
      !editing && expanded && v?.deXuatSua ? h("div", { class: "issue__fix" }, h("span", { class: "issue__fix-label" }, "Đề xuất sửa theo nguồn"), h("p", null, v.deXuatSua)) : null,
      !editing && expanded ? openFix(q).map((f) => h("div", { class: "issue__fix" }, h("span", { class: "issue__fix-label" }, f.message),
        f.suggestedReplacement ? h("p", null, f.suggestedReplacement) : null,
        f.suggestedReplacement ? h("div", null, button("Dùng gợi ý", { small: true, onClick: async (e) => {
          const r = await busy(e.currentTarget, () => quizzes.applyFix(st.qs.id, q.id, f.id));
          if (r) setQuestion(r);
        } })) : null)) : null,
      editing ? null : h("div", { class: "issue__actions" },
        button("Sửa", { kind: "ghost", small: true, iconName: "edit", onClick: () => { st.editing = q.id; render(); } }),
        expanded ? button("Giữ nguyên", { kind: "ghost", small: true, iconName: "check", onClick: (e) => decide(e, q, "accept") }) : null,
        button("Bỏ khỏi đề", { kind: "ghost", small: true, iconName: "x", onClick: (e) => decide(e, q, "reject") })));
  }

  function options(q) {
    if (!q.options?.length) return q.answerText ? h("p", null, h("strong", null, "Đáp án mẫu: "), q.answerText) : null;
    const pa = q.verdict?.phuongAn || {};
    return h("ol", { class: "options" }, q.options.map((o) => {
      const correct = q.type === "mcq" ? o.key === q.correctKey : o.isCorrect;
      return h("li", { class: `option${correct ? " option--correct" : ""}` }, h("span", { class: "option__key" }, o.key),
        h("div", null, h("div", null, o.text),
          correct ? h("span", { class: "tag tag--ok" }, q.type === "mcq" ? "Đáp án" : "Đúng") : null,
          !correct && pa[o.key] === "dung" ? h("span", { class: "tag tag--bad" }, "Cũng đúng theo nguồn") : null,
          !correct && o.misconception ? h("div", { class: "option__why" }, "Nhắm vào lỗi: ", o.misconception) : null));
    }));
  }

  function editForm(q) {
    const stem = h("textarea", { class: "input", rows: 3, value: q.stem, "aria-label": "Đề bài" });
    const opts = (q.options || []).map((o) => h("input", { class: "input", value: o.text, "aria-label": `Phương án ${o.key}` }));
    const key = h("select", { class: "input input--auto", "aria-label": "Đáp án đúng" },
      (q.options || []).map((o) => h("option", { value: o.key, selected: o.key === q.correctKey }, o.key)));
    const expl = h("textarea", { class: "input", rows: 3, value: q.explanation || "", "aria-label": "Giải thích" });
    const save = button("Lưu và kiểm lại", { kind: "primary", small: true, type: "submit" });
    return h("form", { class: "stack stack--sm", onSubmit: async (e) => {
      e.preventDefault();
      const patch = { stem: stem.value.trim(), explanation: expl.value.trim(),
        options: (q.options || []).map((o, i) => ({ ...o, text: opts[i].value.trim() })) };
      if (q.type === "mcq") patch.correctKey = key.value;
      const r = await busy(save, async () => {
        await quizzes.update(st.qs.id, q.id, patch);
        return quizzes.reverify(st.qs.id, q.id);
      });
      if (!r) return;
      setTrace(`Kiểm lại câu ${q.number} sau khi sửa`, r.trace);
      st.editing = null;
      setQuestion(r.data);
    } },
    stem, (q.options || []).map((o, i) => h("label", { class: "row" }, h("span", { class: "option__key" }, o.key), opts[i])),
    q.type === "mcq" ? h("label", { class: "row small" }, "Đáp án đúng", key) : null, expl,
    h("div", { class: "row" }, save, button("Huỷ", { kind: "ghost", small: true, onClick: () => { st.editing = null; render(); } })));
  }

  async function decide(e, q, action) {
    const r = await busy(e.currentTarget, () => quizzes.decide(st.qs.id, q.id, action));
    if (!r) return;
    setQuestion(r);
    if (action === "reject") {
      toast(`Đã bỏ câu ${q.number} khỏi đề`, "info", 7000, { label: "Hoàn tác",
        run: async () => setQuestion(await quizzes.decide(st.qs.id, q.id, "reset")) });
    }
  }

  return () => { alive = false; };
}
