/* Cited source chunk next to a claim, with words shared with the claim highlighted (text nodes only). */
import { h } from "../core/dom.js";

const STOP = new Set("và của là các những được có trong một cho với từ này đó khi thì để không theo the and of to in is".split(" "));

function words(text) {
  return new Set((text || "").toLowerCase().normalize("NFC").match(/[\p{L}\p{N}]+/gu)?.filter((w) => w.length > 2 && !STOP.has(w)) || []);
}

export function highlighted(text, claim) {
  const keys = words(claim);
  const parts = (text || "").split(/([\p{L}\p{N}]+)/u);
  return parts.map((p) => (keys.has(p.toLowerCase()) ? h("mark", null, p) : p));
}

export function sourcePanel(nguon, claim, { title = "Đoạn nguồn trích dẫn" } = {}) {
  if (!nguon) {
    return h("div", { class: "source source--none" }, h("div", { class: "source__head" }, title),
      h("p", { class: "muted" }, "Không có đoạn nguồn nào được trích cho câu này."));
  }
  return h("div", { class: "source" },
    h("div", { class: "source__head" }, title, h("code", { class: "source__id" }, nguon.id)),
    nguon.headingPath?.length ? h("div", { class: "source__path" }, nguon.headingPath.join(" › ")) : null,
    nguon.pages?.length ? h("div", { class: "source__pages muted small" }, `Trang ${nguon.pages.join(", ")}`) : null,
    h("blockquote", { class: "source__text" }, highlighted(nguon.text, claim)),
    (nguon.imageIds?.length || nguon.tableIds?.length)
      ? h("div", { class: "muted small" }, [nguon.imageIds?.length ? `${nguon.imageIds.length} hình` : null,
        nguon.tableIds?.length ? `${nguon.tableIds.length} bảng` : null].filter(Boolean).join(" · "), " trong đoạn này")
      : null);
}
