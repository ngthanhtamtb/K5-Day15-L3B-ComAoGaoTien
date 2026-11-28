/* "Agent đã kiểm gì": hidden until a model-backed action ran, then a small button opens the
 * details (steps, provider/model, tokens, cost). Shows only numbers the API returned. */
import { h, icon, replace } from "../core/dom.js";
import { fmtCost, fmtNumber } from "../core/format.js";
import { store } from "../core/store.js";

const RULE = {
  injection: "Câu chứa chỉ dẫn chèn → tự loại, không gọi model",
  no_evidence: "Không có đoạn nguồn liên quan → không gọi model",
};

export function agentPanel() {
  let open = false;
  const body = h("div", { class: "stack stack--sm" });
  const fab = h("button", { class: "agent__fab", type: "button", hidden: true, "aria-expanded": "false",
    onClick: () => setOpen(!open) }, icon("shield", 16), h("span", null, "Agent đã kiểm gì"));
  const panel = h("aside", { class: "agent__panel", hidden: true, "aria-label": "Agent đã kiểm gì" },
    h("div", { class: "row row--between" }, h("h2", null, "Agent đã kiểm gì"),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Đóng", onClick: () => setOpen(false) }, icon("x", 18))),
    body);

  function setOpen(v) {
    open = v;
    panel.hidden = !v;
    fab.setAttribute("aria-expanded", String(v));
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && open) setOpen(false); });

  store.subscribe((s) => {
    const t = s.trace;
    fab.hidden = !t;
    if (!t) return;
    const sum = t.summary;
    fab.classList.toggle("has-errors", Boolean(sum.errors?.length));
    const calls = sum.steps.filter((x) => x.kind === "model_call");
    replace(body,
      h("p", { class: "small" }, t.label),
      h("div", { class: "agent__grid" },
        cell("Lần gọi model", fmtNumber(sum.model_calls)), cell("Token vào / ra", `${fmtNumber(sum.tokens_in)} / ${fmtNumber(sum.tokens_out)}`),
        cell("Chi phí", fmtCost(sum.cost_usd, "USD")), cell("Thời gian", `${sum.elapsed_s}s`)),
      calls.length ? h("p", { class: "small muted" }, "Model: ", [...new Set(calls.map((c) => `${c.provider} · ${c.model}`))].join(", ")) : null,
      calls.some((c) => c.fallback) ? h("p", { class: "small" }, "Provider đầu tiên lỗi nên đã tự chuyển sang provider dự phòng.") : null,
      h("ol", { class: "agent__steps" }, sum.steps.map((st) => h("li", null,
        st.kind === "model_call" ? `Gọi model (${st.task}) · ${fmtNumber(st.tokens_in)}→${fmtNumber(st.tokens_out)} token · ${st.latency_s}s`
          : st.kind === "rule" ? `${RULE[st.rule] || st.rule} (câu ${st.index + 1})`
            : `Lỗi ${st.provider || ""}: ${st.message || ""}`))));
  });

  function cell(k, v) {
    return h("div", null, k, h("strong", null, v));
  }

  return { el: h("div", null, fab, panel) };
}
