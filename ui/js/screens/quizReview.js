/* Quiz review (gates 1–2): per-question verdict (all options checked against the source),
 * correct answer, distractor misconceptions, evaluation fixes, edit + re-verify, decide, submit, PDF. */
import { quizzes } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { setTrace } from "../core/store.js";
import { sourcePanel } from "../components/sourcePanel.js";
import { badge, busy, button, decisionChip, errorBox, pageHeader, progressBar, spinner, stepper } from "../components/ui.js";
import { QUIZ_STEPS } from "./quizNew.js";

const DEPTH = { tinh_huong: "Tình huống", nhieu_buoc: "Nhiều bước", doc_bang: "Đọc bảng", doc_hinh: "Đọc hình", co_ban: "Cơ bản" };

export function mount(el, { params }) {
  const st = { qs: null, sel: 0, editing: false };
  replace(el, spinner("Đang mở quiz…"));
  load();

  async function load() {
    try {
      st.qs = await quizzes.get(params.id);
      render();
    } catch (e) {
      replace(el, errorBox(e, load));
    }
  }

  function replaceQuestion(q) {
    st.qs.questions = st.qs.questions.map((x) => (x.id === q.id ? q : x));
  }

  function render() {
    const qs = st.qs;
    const qList = qs.questions;
    const decided = qList.filter((q) => q.decision !== "chua_quyet").length;
    const locked = qs.status === "cho_duyet";
    const q = qList[st.sel];

    replace(el,
      stepper(QUIZ_STEPS, locked ? 2 : 1),
      pageHeader(qs.title, `${qList.length} câu · engine ${qs.engine}`, [
        button("Chạy kiểm định", { iconName: "shield", disabled: locked, onClick: async (e) => {
          const r = await busy(e.currentTarget, () => quizzes.evaluate(qs.id, true), { ok: "Đã kiểm định: xem gợi ý sửa ở từng câu" });
          if (r) { st.qs = r; render(); }
        } }),
        h("a", { class: "btn btn--secondary", href: quizzes.pdfUrl(qs.id, false), target: "_blank", rel: "noopener" }, icon("download", 17), h("span", null, "PDF đề")),
        h("a", { class: "btn btn--secondary", href: quizzes.pdfUrl(qs.id, true), target: "_blank", rel: "noopener" }, icon("download", 17), h("span", null, "PDF đáp án")),
        button(locked ? "Đã gửi chờ duyệt" : "Gửi chờ duyệt", { kind: "primary", iconName: "check", disabled: locked || decided < qList.length,
          onClick: async (e) => {
            const r = await busy(e.currentTarget, () => quizzes.submit(qs.id), { ok: "Bộ quiz đã ở trạng thái chờ duyệt" });
            if (r) { st.qs = r; render(); }
          } }),
      ]),
      qs.warnings?.length ? h("div", { class: "alert alert--warn" }, qs.warnings.join(" · ")) : null,
      h("div", { class: "toolbar" }, progressBar(qList.length ? (decided / qList.length) * 100 : 0, `Đã quyết định ${decided}/${qList.length}`)),
      !q ? h("p", { class: "muted" }, "Bộ quiz không có câu nào.") :
        h("div", { class: "split" },
          h("div", { class: "split__list", role: "listbox", "aria-label": "Các câu hỏi" }, qList.map((x, i) => h("button", {
            class: `claim${i === st.sel ? " is-selected" : ""}`, type: "button", role: "option", "aria-selected": String(i === st.sel),
            onClick: () => { st.sel = i; st.editing = false; render(); },
          }, h("span", { class: "claim__id mono" }, `Câu ${x.number}`), h("span", { class: "claim__text" }, x.stem),
          h("span", { class: "claim__meta" }, x.verdict ? badge(x.verdict.nhan, { short: true }) : null, decisionChip(x.decision))))),
          detail(q, locked)));
  }

  function detail(q, locked) {
    const v = q.verdict;
    const errors = (q.fixes || []).filter((f) => !f.fixed);
    return h("div", { class: "split__detail" },
      h("div", { class: "row row--between" },
        h("span", { class: "muted small" }, [q.code, q.bloom, DEPTH[q.depth], q.type].filter(Boolean).join(" · ")),
        h("div", { class: "row" }, v ? badge(v.nhan) : h("span", { class: "chip chip--muted" }, "Chưa kiểm nguồn"), decisionChip(q.decision))),
      st.editing && !locked ? editForm(q) : view(q),
      v ? h("div", { class: "detail__block" }, h("h3", null, "Kết quả kiểm nguồn"), h("p", null, v.lyDo || "—"),
        v.phuongAn ? h("div", { class: "row row--wrap" }, Object.entries(v.phuongAn).map(([k, s]) =>
          h("span", { class: `chip ${s === "dung" ? "chip--ok" : s === "sai" ? "chip--bad" : "chip--muted"}` }, `${k}: ${s === "dung" ? "đúng" : s === "sai" ? "sai" : "không rõ"}`))) : null,
        v.deXuatSua ? h("div", { class: "detail__block detail__block--fix" }, h("h3", null, "Đề xuất sửa"), h("p", null, v.deXuatSua)) : null,
        sourcePanel(v.nguon, q.stem)) : null,
      errors.length ? h("div", { class: "detail__block" }, h("h3", null, `Gợi ý từ kiểm định (${errors.length})`),
        errors.map((f) => h("div", { class: `fix fix--${f.severity}` }, h("p", null, h("strong", null, f.kind), " · ", f.message),
          f.suggestedReplacement ? h("p", { class: "muted small" }, `${f.targetField} → ${f.suggestedReplacement}`) : null,
          !locked && f.suggestedReplacement ? button("Áp dụng sửa", { small: true, onClick: (e) => applyFix(e, q, f) }) : null))) : null,
      (q.fixes || []).some((f) => f.fixed) && !locked ? h("div", { class: "row" }, (q.fixes || []).filter((f) => f.fixed).map((f) =>
        button(`Hoàn tác: ${f.kind}`, { small: true, iconName: "undo", onClick: (e) => applyFix(e, q, f, true) }))) : null,
      locked ? null : h("div", { class: "actions" },
        button("Chấp nhận câu", { kind: "primary", iconName: "check", onClick: (e) => decide(e, q, "accept") }),
        button("Từ chối câu", { iconName: "x", onClick: (e) => decide(e, q, "reject") }),
        st.editing ? null : button("Sửa câu", { iconName: "edit", onClick: () => { st.editing = true; render(); } }),
        button("Kiểm lại nguồn", { iconName: "shield", onClick: (e) => reverify(e, q) }),
        q.decision !== "chua_quyet" ? button("Bỏ quyết định", { iconName: "undo", onClick: (e) => decide(e, q, "reset") }) : null));
  }

  function view(q) {
    return h("div", { class: "stack" },
      h("h2", { class: "detail__text" }, q.stem),
      q.options?.length ? h("ol", { class: "options" }, q.options.map((o) => {
        const correct = q.type === "mcq" ? o.key === q.correctKey : o.isCorrect;
        return h("li", { class: `option${correct ? " option--correct" : ""}` },
          h("span", { class: "option__key" }, o.key), h("div", null, h("div", null, o.text),
            correct ? h("span", { class: "chip chip--ok" }, q.type === "mcq" ? "Đáp án" : "Đúng") : null,
            !correct && o.misconception ? h("div", { class: "muted small" }, "Nhắm vào lỗi hiểu sai: ", o.misconception) : null));
      })) : null,
      q.answerText ? h("p", null, h("strong", null, "Đáp án mẫu: "), q.answerText) : null,
      q.explanation ? h("details", { open: true }, h("summary", null, "Giải thích"), h("p", null, q.explanation)) : null);
  }

  function editForm(q) {
    const stem = h("textarea", { class: "input textarea", rows: 3, value: q.stem, "aria-label": "Đề bài" });
    const opts = (q.options || []).map((o) => h("input", { class: "input", value: o.text, "aria-label": `Phương án ${o.key}` }));
    const key = h("select", { class: "input input--sm", "aria-label": "Đáp án đúng" },
      (q.options || []).map((o) => h("option", { value: o.key, selected: o.key === q.correctKey }, o.key)));
    const expl = h("textarea", { class: "input textarea", rows: 3, value: q.explanation || "", "aria-label": "Giải thích" });
    return h("form", { class: "stack", onSubmit: async (e) => {
      e.preventDefault();
      const patch = { stem: stem.value.trim(), explanation: expl.value.trim(),
        options: (q.options || []).map((o, i) => ({ ...o, text: opts[i].value.trim() })) };
      if (q.type === "mcq") patch.correctKey = key.value;
      const saved = await busy(e.submitter, () => quizzes.update(st.qs.id, q.id, patch));
      if (!saved) return;
      replaceQuestion(saved);
      st.editing = false;
      await reverify(null, saved);            // gate 2: an edited question is always re-checked
    } },
    h("label", { class: "field__label" }, "Đề bài"), stem,
    (q.options || []).map((o, i) => h("label", { class: "inline-field inline-field--wide" }, o.key, opts[i])),
    q.type === "mcq" ? h("label", { class: "inline-field" }, "Đáp án đúng", key) : null,
    h("label", { class: "field__label" }, "Giải thích"), expl,
    h("div", { class: "row" }, button("Lưu & kiểm lại", { kind: "primary", type: "submit" }),
      button("Huỷ", { onClick: () => { st.editing = false; render(); } })));
  }

  async function decide(e, q, action) {
    const r = await busy(e.currentTarget, () => quizzes.decide(st.qs.id, q.id, action));
    if (!r) return;
    replaceQuestion(r);
    if (action !== "reset") {
      const next = st.qs.questions.findIndex((x, i) => i > st.sel && x.decision === "chua_quyet");
      if (next >= 0) st.sel = next;
    }
    render();
  }

  async function reverify(e, q) {
    const r = await busy(e?.currentTarget, () => quizzes.reverify(st.qs.id, q.id));
    if (!r) return render();
    setTrace(`Kiểm lại nguồn câu ${q.number}`, r.trace);
    replaceQuestion(r.data);
    render();
  }

  async function applyFix(e, q, f, undo = false) {
    const r = await busy(e.currentTarget, () => quizzes.applyFix(st.qs.id, q.id, f.id, undo));
    if (r) { replaceQuestion(r); render(); }
  }
}
