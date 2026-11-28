/* Quiz setup: document, size, question types, Bloom mix, depth. Generation is one model call. */
import { documents, quizzes } from "../api/edu.js";
import { h, replace } from "../core/dom.js";
import { go } from "../core/router.js";
import { prefs, setTrace } from "../core/store.js";
import { busy, button, card, empty, errorBox, pageHeader, spinner, stepper } from "../components/ui.js";

export const QUIZ_STEPS = ["Thiết lập", "Kiểm từng câu (cổng 1–2)", "Chờ duyệt & xuất PDF"];
const TYPES = [["mcq", "Trắc nghiệm 4 lựa chọn"], ["true_false", "Đúng / Sai (a–d)"], ["short_answer", "Trả lời ngắn"]];
const BLOOM = ["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"];

export function mount(el, { query }) {
  replace(el, spinner());
  documents.list().then(render).catch((e) => replace(el, errorBox(e, () => mount(el, { query }))));

  function render(docs) {
    if (!docs.length) return replace(el, pageHeader("Tạo quiz"), empty("Cần tải tài liệu gốc trước.", button("Về thư viện", { kind: "primary", onClick: () => go("/") })));
    const saved = prefs.get("quiz", { n: 10, types: ["mcq"], bloom: [40, 30, 20, 10], depth: true });
    const docSel = h("select", { class: "input", id: "q-doc" }, docs.map((d) => h("option", { value: d.docId, selected: d.docId === query.doc }, d.filename)));
    const title = h("input", { class: "input", id: "q-title", placeholder: "VD: Quiz buổi 7 — RAG" });
    const n = h("input", { class: "input input--sm", id: "q-n", type: "number", min: 1, max: 60, value: saved.n });
    const types = TYPES.map(([v, label]) => h("label", { class: "check" },
      h("input", { type: "checkbox", value: v, checked: saved.types.includes(v) }), label));
    const bloom = BLOOM.map((b, i) => h("label", { class: "inline-field" }, b,
      h("input", { class: "input input--xs", type: "number", min: 0, max: 100, value: saved.bloom[i], "aria-label": `Tỉ lệ ${b}` })));
    const depth = h("input", { type: "checkbox", checked: saved.depth, id: "q-depth" });
    const go_ = button("Sinh quiz & kiểm nguồn", { kind: "primary", type: "submit" });

    const form = h("form", { class: "stack", onSubmit: async (e) => {
      e.preventDefault();
      const picked = types.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
      if (!picked.length) return types[0].querySelector("input").focus();
      const mix = Object.fromEntries(BLOOM.map((b, i) => [b, Number(bloom[i].querySelector("input").value) || 0]));
      const body = { numQuestions: Number(n.value), questionTypes: picked, bloomMix: mix, depth: depth.checked,
        verify: true, title: title.value.trim() || null };
      prefs.set("quiz", { n: body.numQuestions, types: picked, bloom: Object.values(mix), depth: depth.checked });
      const res = await busy(go_, () => quizzes.generate(docSel.value, body));
      if (!res) return;
      setTrace(`Sinh quiz “${res.title}” và kiểm từng phương án`, res.trace);
      go(`/quizzes/${res.id}`);
    } },
    field("Tài liệu gốc", docSel), field("Tên bộ quiz", title), field("Số câu", n),
    h("fieldset", { class: "fieldset" }, h("legend", null, "Loại câu"), h("div", { class: "row row--wrap" }, types)),
    h("fieldset", { class: "fieldset" }, h("legend", null, "Tỉ lệ mức độ Bloom (%)"), h("div", { class: "row row--wrap" }, bloom)),
    h("label", { class: "check" }, depth, h("span", null, h("strong", null, "Câu hỏi có chiều sâu"),
      " — tình huống, nhiều bước (≥ 2 đoạn nguồn), đọc bảng / hình; mỗi phương án nhiễu ghi rõ lỗi hiểu sai nó nhắm tới")),
    h("div", { class: "row" }, go_, h("span", { class: "muted small" }, "Có thể mất 20–60 giây.")));

    replace(el, stepper(QUIZ_STEPS, 0), pageHeader("Tạo quiz trắc nghiệm", "Mỗi câu gắn đoạn nguồn và được kiểm từng phương án trước khi tới tay bạn."),
      h("div", { class: "grid grid--main" }, card(null, form), card("Sau khi sinh", h("ul", { class: "bullets" },
        h("li", null, "Mỗi câu có nhãn Khớp / Sai / Thiếu nguồn sau khi kiểm cả 4 phương án (bắt được câu có 2 đáp án đúng)."),
        h("li", null, "Bạn chấp nhận, từ chối hoặc sửa từng câu; câu đã sửa được kiểm lại."),
        h("li", null, "Xuất PDF đề và đáp án (kèm giải thích, nguồn) chỉ gồm câu đã chấp nhận.")))));
  }
}

function field(label, control) {
  return h("label", { class: "field", for: control.id }, h("span", { class: "field__label" }, label), control);
}
