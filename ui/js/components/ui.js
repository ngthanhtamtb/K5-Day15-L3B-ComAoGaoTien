/* Building blocks shared by every screen (design-system/scriptguard). */
import { h, icon } from "../core/dom.js";
import { toast } from "../core/store.js";

/** Source labels: always a dot + a word (never colour alone). */
export const LABELS = {
  KHOP_NGUON: { text: "Khớp nguồn", tone: "ok" },
  SAI_NGUON: { text: "Sai so với nguồn", tone: "bad" },
  THIEU_NGUON: { text: "Không có trong tài liệu", tone: "warn" },
  TU_CHOI: { text: "Chỉ dẫn chèn — tự loại", tone: "refuse" },
  DAN_DAT: { text: "Câu dẫn dắt", tone: "muted" },   // built from slide titles, carries no new fact
};

export function tag(label) {
  const meta = LABELS[label] || { text: label || "Chưa kiểm", tone: "muted" };
  return h("span", { class: `tag tag--${meta.tone}` }, meta.text);
}

export function button(text, { onClick, kind = "secondary", iconName, disabled, title, type = "button", small, label } = {}) {
  return h("button", { class: `btn btn--${kind}${small ? " btn--sm" : ""}`, type, disabled, title,
    "aria-label": label || null, onClick },
  iconName ? icon(iconName, small ? 16 : 18) : null, text ? h("span", null, text) : null);
}

export function linkButton(text, onClick) {
  return h("button", { class: "link-btn", type: "button", onClick }, text);
}

/** Busy state on the button + error toast with the backend message. Returns the result or undefined. */
export async function busy(btn, fn, { ok } = {}) {
  const prev = btn?.disabled;
  if (btn) { btn.disabled = true; btn.classList.add("is-busy"); btn.setAttribute("aria-busy", "true"); }
  try {
    const result = await fn();
    if (ok) toast(ok, "ok");
    return result;
  } catch (e) {
    toast(e.message || String(e), "bad", 8000);
    return undefined;
  } finally {
    if (btn && btn.isConnected) { btn.disabled = prev; btn.classList.remove("is-busy"); btn.removeAttribute("aria-busy"); }
  }
}

export function pageHead({ eyebrow, title, subtitle, actions }) {
  return h("header", { class: "page-head" },
    h("div", { class: "page-head__text" }, eyebrow ? h("span", { class: "eyebrow" }, eyebrow) : null,
      h("h1", null, title), subtitle ? h("p", { class: "muted" }, subtitle) : null),
    actions ? h("div", { class: "page-head__actions" }, actions) : null);
}

/** Progressive disclosure: a native <details>. `flat` = inline text toggle instead of a card. */
export function disclosure(summary, body, { open = false, flat = false, onToggle } = {}) {
  const d = h("details", { class: `more${flat ? " more--flat" : ""}`, open },
    h("summary", null, summary), h("div", { class: "more__body" }, body));
  if (onToggle) d.addEventListener("toggle", () => onToggle(d.open));
  return d;
}

export function empty(text, action) {
  return h("div", { class: "empty" }, h("p", null, text), action || null);
}

export function notice(text, tone = "", iconName = "info") {
  return h("div", { class: `notice${tone ? ` notice--${tone}` : ""}`, role: tone === "bad" ? "alert" : null }, icon(iconName, 16), h("div", null, text));
}

export function skeleton(lines = 3, height = 18) {
  return h("div", { class: "stack stack--sm", "aria-busy": "true", "aria-label": "Đang tải" },
    Array.from({ length: lines }, (_, i) => h("div", { class: "skeleton", style: { height: `${height}px`, width: `${100 - i * 12}%` } })));
}

export function errorState(err, retry) {
  return h("div", { class: "empty", role: "alert" }, h("p", null, err.message || String(err)),
    retry ? button("Thử lại", { onClick: retry }) : null);
}

export function progress(pct, label) {
  return h("div", { class: "progress" },
    label ? h("div", { class: "row row--between small" }, h("span", null, label), h("span", { class: "muted" }, `${Math.round(pct)}%`)) : null,
    h("div", { class: "progress__track", role: "progressbar", "aria-valuenow": Math.round(pct), "aria-valuemin": 0, "aria-valuemax": 100 },
      h("div", { class: "progress__bar", style: { width: `${Math.max(2, Math.min(100, pct))}%` } })));
}

/** One-glance share of each label + legend with counts (text, not colour, carries the meaning). */
export function healthBar(counts, order = ["KHOP_NGUON", "SAI_NGUON", "THIEU_NGUON", "TU_CHOI"]) {
  const total = order.reduce((s, k) => s + (counts[k] || 0), 0) || 1;
  return h("div", { class: "health" },
    h("div", { class: "health__bar", "aria-hidden": "true" }, order.filter((k) => counts[k]).map((k) =>
      h("span", { class: `health__${LABELS[k].tone}`, style: { width: `${(counts[k] / total) * 100}%` } }))),
    h("div", { class: "health__legend" }, order.filter((k) => counts[k]).map((k) =>
      h("span", { class: `tag tag--${LABELS[k].tone}` }, `${counts[k]} ${LABELS[k].text.toLowerCase()}`))));
}
