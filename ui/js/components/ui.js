/* Small building blocks shared by every screen. */
import { h, icon } from "../core/dom.js";
import { toast } from "../core/store.js";

export const LABELS = {
  KHOP_NGUON: { text: "Khớp nguồn", tone: "ok" },
  SAI_NGUON: { text: "Sai / mâu thuẫn nguồn", tone: "bad" },
  THIEU_NGUON: { text: "Thiếu nguồn", tone: "warn" },
  TU_CHOI: { text: "Từ chối xử lý", tone: "refuse" },
};

export const DECISIONS = {
  chua_quyet: { text: "Chưa quyết định", tone: "muted" },
  chap_nhan: { text: "Đã chấp nhận", tone: "ok" },
  tu_choi_cau: { text: "Đã từ chối", tone: "refuse" },
  da_sua: { text: "Đã sửa", tone: "info" },
};

export function badge(label, { short = false } = {}) {
  const meta = LABELS[label] || { text: label || "—", tone: "muted" };
  return h("span", { class: `badge badge--${meta.tone}`, title: meta.text },
    short ? meta.text.split(" /")[0] : meta.text);
}

export function decisionChip(decision) {
  const meta = DECISIONS[decision] || DECISIONS.chua_quyet;
  return h("span", { class: `chip chip--${meta.tone}` }, meta.text);
}

export function button(text, { onClick, kind = "secondary", iconName, disabled, title, type = "button", small } = {}) {
  return h("button", { class: `btn btn--${kind}${small ? " btn--sm" : ""}`, type, disabled, title, onClick },
    iconName ? icon(iconName, small ? 15 : 17) : null, text ? h("span", null, text) : null);
}

/** Run an async action with a busy button and error toast. Returns the action's result (or undefined on error). */
export async function busy(btn, fn, { ok } = {}) {
  const prev = btn?.disabled;
  if (btn) {
    btn.disabled = true;
    btn.classList.add("is-busy");
  }
  try {
    const result = await fn();
    if (ok) toast(ok, "ok");
    return result;
  } catch (e) {
    toast(e.message || String(e), "bad", 7000);
    return undefined;
  } finally {
    if (btn && btn.isConnected) {
      btn.disabled = prev;
      btn.classList.remove("is-busy");
    }
  }
}

export function card(title, ...children) {
  return h("section", { class: "card" }, title ? h("h2", { class: "card__title" }, title) : null, children);
}

export function empty(text, action) {
  return h("div", { class: "empty" }, icon("info", 22), h("p", null, text), action || null);
}

export function spinner(text = "Đang tải…") {
  return h("div", { class: "loading", role: "status" }, h("span", { class: "spinner", "aria-hidden": "true" }), text);
}

export function errorBox(err, retry) {
  return h("div", { class: "alert alert--bad", role: "alert" },
    h("strong", null, "Không tải được dữ liệu. "), err.message || String(err),
    retry ? h("div", { class: "alert__actions" }, button("Thử lại", { onClick: retry, small: true })) : null);
}

export function progressBar(pct, label) {
  return h("div", { class: "progress", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100 },
    h("div", { class: "progress__bar", style: { width: `${Math.max(0, Math.min(100, pct))}%` } }),
    label ? h("span", { class: "progress__label" }, label) : null);
}

/** Pill stepper used at the top of each flow ("1 Nhập · 2 Rà soát · 3 Slide · 4 Giọng · 5 Gửi"). */
export function stepper(labels, current) {
  return h("ol", { class: "stepper", "aria-label": "Các bước" },
    labels.map((l, i) => h("li", { class: `stepper__item${i < current ? " is-done" : ""}${i === current ? " is-current" : ""}`,
      "aria-current": i === current ? "step" : null },
    h("span", { class: "stepper__num" }, i < current ? icon("check", 13) : String(i + 1)), l)));
}

export function pageHeader(title, subtitle, actions) {
  return h("header", { class: "page-head" },
    h("div", null, h("h1", null, title), subtitle ? h("p", { class: "muted" }, subtitle) : null),
    actions ? h("div", { class: "page-head__actions" }, actions) : null);
}

export function stat(label, value) {
  return h("div", { class: "stat" }, h("div", { class: "stat__value" }, value), h("div", { class: "stat__label" }, label));
}
