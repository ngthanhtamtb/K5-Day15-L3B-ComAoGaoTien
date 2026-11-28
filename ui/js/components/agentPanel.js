/* "Agent verify" panel: what the backend actually ran for the last model-backed action
 * (steps, provider/model, tokens, cost, errors). Shows only numbers the API returned. */
import { h, icon, replace } from "../core/dom.js";
import { fmtCost, fmtNumber } from "../core/format.js";
import { store } from "../core/store.js";

const KIND = {
  model_call: "Gọi model",
  rule: "Luật cố định (không gọi model)",
  error: "Lỗi",
};

const RULE = {
  injection: "Phát hiện chỉ dẫn chèn → Từ chối",
  no_evidence: "Không có đoạn nguồn nào liên quan → Thiếu nguồn",
};

export function agentPanel() {
  let open = false;
  const body = h("div", { class: "agent__body" });
  const toggle = h("button", { class: "agent__fab", type: "button", "aria-expanded": "false", onClick: () => setOpen(!open) },
    icon("shield", 18), h("span", null, "Agent đã kiểm gì"));
  const panel = h("aside", { class: "agent__panel", "aria-label": "Agent đã kiểm gì", hidden: true },
    h("div", { class: "agent__head" }, h("h2", null, "Agent đã kiểm gì"),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Đóng", onClick: () => setOpen(false) }, icon("x", 18))),
    body);
  const el = h("div", { class: "agent" }, toggle, panel);

  function setOpen(v) {
    open = v;
    panel.hidden = !v;
    toggle.setAttribute("aria-expanded", String(v));
  }

  store.subscribe((s) => render(s.trace));
  render(null);

  function render(trace) {
    toggle.classList.toggle("has-errors", Boolean(trace?.summary?.errors?.length));
    if (!trace) {
      return replace(body, h("p", { class: "muted" },
        "Chưa có thao tác nào gọi model. Khi bạn đối chiếu kịch bản, sinh quiz hoặc kiểm lại một câu, các bước đã chạy hiện ở đây."));
    }
    const s = trace.summary;
    const calls = s.steps.filter((x) => x.kind === "model_call");
    const providers = [...new Set(calls.map((c) => `${c.provider} · ${c.model}`))];
    replace(body,
      h("p", { class: "agent__label" }, trace.label),
      h("div", { class: "agent__stats" },
        statLine("Lần gọi model", fmtNumber(s.model_calls)),
        statLine("Token vào / ra", `${fmtNumber(s.tokens_in)} / ${fmtNumber(s.tokens_out)}`),
        statLine("Chi phí", fmtCost(s.cost_usd, "USD")),
        statLine("Thời gian", `${s.elapsed_s}s`)),
      providers.length ? h("p", { class: "muted small" }, "Model đã trả lời: ", providers.join(", ")) : null,
      calls.some((c) => c.fallback) ? h("p", { class: "alert alert--warn small" },
        "Provider đầu tiên lỗi, hệ thống đã tự chuyển sang provider dự phòng.") : null,
      h("h3", null, "Quy trình đã chạy"),
      h("ol", { class: "agent__steps" }, s.steps.map((st) => h("li", { class: `agent__step agent__step--${st.kind}` },
        h("strong", null, KIND[st.kind] || st.kind),
        st.kind === "model_call" ? ` · ${st.task} · ${st.provider}:${st.model} · ${fmtNumber(st.tokens_in)}→${fmtNumber(st.tokens_out)} token · ${st.latency_s}s` : null,
        st.kind === "rule" ? ` · ${RULE[st.rule] || st.rule} (mục ${st.index})` : null,
        st.kind === "error" ? ` · ${st.provider || ""} ${st.message || ""}` : null))),
      h("h3", null, "Kiểm tra an toàn"),
      h("ul", { class: "agent__checks" },
        h("li", null, icon("check", 14), "Nội dung kịch bản được coi là dữ liệu, không phải lệnh"),
        h("li", null, icon("check", 14), "Mã đoạn nguồn do model đưa ra được code kiểm lại"),
        h("li", null, icon("check", 14), "Không có thao tác xuất bản — trạng thái cuối là chờ duyệt")));
  }

  function statLine(k, v) {
    return h("div", { class: "agent__stat" }, h("span", null, k), h("strong", null, v));
  }

  return { el };
}
