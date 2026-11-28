/* Screen 1 · Draft in: paste an existing script or generate one from the document. */
import { documents, scripts } from "../api/edu.js";
import { h, replace } from "../core/dom.js";
import { go } from "../core/router.js";
import { setTrace } from "../core/store.js";
import { button, busy, card, empty, errorBox, pageHeader, spinner, stepper } from "../components/ui.js";

export const SCRIPT_STEPS = ["Nhập bản nháp", "Rà soát (cổng 1)", "Slide & giọng đọc", "Kiểm lại (cổng 2)", "Chờ duyệt"];

const SAMPLE = `Slide 1: Nền tảng LLM
LLM sinh văn bản theo vòng lặp tự hồi quy, mỗi bước dự đoán một token kế tiếp.
Tăng temperature giúp câu trả lời của model tập trung và ổn định hơn.
Slide 2: Prompt
Chain-of-thought làm tăng số token đầu ra, kéo theo tăng chi phí và độ trễ.`;

export function mount(el, { query }) {
  replace(el, spinner());
  let mode = "paste";
  documents.list().then((docs) => render(docs)).catch((e) => replace(el, errorBox(e, () => mount(el, { query }))));

  function render(docs) {
    if (!docs.length) {
      return replace(el, pageHeader("Tạo kịch bản"), empty("Cần tải tài liệu gốc trước.",
        button("Về thư viện", { onClick: () => go("/"), kind: "primary" })));
    }
    const docSel = h("select", { id: "doc", class: "input" }, docs.map((d) =>
      h("option", { value: d.docId, selected: d.docId === query.doc }, d.filename)));
    const title = h("input", { id: "title", class: "input", placeholder: "VD: Day 01 — Nền tảng LLM" });
    const text = h("textarea", { id: "draft", class: "input textarea", rows: 14,
      placeholder: "Mỗi slide bắt đầu bằng “Slide N: tiêu đề”; mỗi câu là một đoạn lời đọc.\n\n" + SAMPLE });
    const topic = h("input", { id: "topic", class: "input", placeholder: "VD: Temperature và context window" });
    const nSlides = h("input", { id: "nslides", class: "input input--sm", type: "number", min: 1, max: 30, value: 6 });
    const nSegs = h("input", { id: "nsegs", class: "input input--sm", type: "number", min: 1, max: 6, value: 3 });
    const submit = button(mode === "paste" ? "Bắt đầu đối chiếu" : "Sinh kịch bản & đối chiếu", { kind: "primary", type: "submit" });

    const form = h("form", { class: "stack", onSubmit: (e) => { e.preventDefault(); create(); } },
      field("Tài liệu gốc", docSel), field("Tên kịch bản", title),
      h("div", { class: "segmented", role: "radiogroup", "aria-label": "Cách tạo" },
        seg("paste", "Dán bản nháp có sẵn"), seg("generate", "Sinh từ tài liệu")),
      mode === "paste"
        ? h("div", { class: "stack" }, field("Bản nháp kịch bản", text),
          h("div", null, button("Dùng ví dụ mẫu", { small: true, onClick: () => { text.value = SAMPLE; } })))
        : h("div", { class: "stack" }, field("Chủ đề trong tài liệu", topic),
          h("div", { class: "row" }, field("Số slide", nSlides), field("Đoạn lời đọc / slide", nSegs))),
      h("div", { class: "row" }, submit));

    replace(el, stepper(SCRIPT_STEPS, 0), pageHeader("Đưa bản nháp kịch bản vào rà soát",
      "Hệ thống đối chiếu từng câu với tài liệu gốc và gắn nhãn Khớp / Sai / Thiếu nguồn. Không sửa kịch bản, không tự xuất bản."),
    h("div", { class: "grid grid--main" }, card(null, form), card("ScriptGuard làm được gì",
      h("ul", { class: "bullets" },
        h("li", null, "Chỉ kiểm đối chiếu với tài liệu gốc đã tải lên, không dùng kiến thức ngoài."),
        h("li", null, "Câu sai nguồn có lý do và câu đề xuất sửa kèm mã đoạn."),
        h("li", null, "Câu chứa chỉ dẫn gửi cho hệ thống (vd “bỏ qua bước duyệt”) bị từ chối, không làm theo."),
        h("li", null, "Bạn quyết định từng câu; trạng thái cuối luôn là chờ duyệt.")))));

    function seg(value, label) {
      return h("button", { type: "button", role: "radio", "aria-checked": String(mode === value),
        class: `segmented__opt${mode === value ? " is-active" : ""}`, onClick: () => { mode = value; render(docs); } }, label);
    }

    async function create() {
      const body = { docId: docSel.value, title: title.value.trim() || null };
      if (mode === "paste") {
        if (!text.value.trim()) return text.focus();
        body.noiDung = text.value;
      } else {
        if (!topic.value.trim()) return topic.focus();
        Object.assign(body, { chuDe: topic.value.trim(), soSlide: Number(nSlides.value), doanMoiSlide: Number(nSegs.value) });
      }
      const res = await busy(submit, () => scripts.create(body));
      if (!res) return;
      setTrace(`Đối chiếu kịch bản “${res.data.title}”`, res.trace);
      go(`/scripts/${res.data.id}`);
    }
  }
}

function field(label, control) {
  return h("label", { class: "field", for: control.id }, h("span", { class: "field__label" }, label), control);
}
