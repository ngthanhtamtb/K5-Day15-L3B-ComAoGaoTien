/* The cited source chunk, with words shared with the claim highlighted (text nodes only). */
import { h } from "../core/dom.js";

const STOP = new Set("và của là các những được có trong một cho với từ này đó khi thì để không theo the and of to in is".split(" "));

function words(text) {
  return new Set((text || "").toLowerCase().normalize("NFC").match(/[\p{L}\p{N}]+/gu)?.filter((w) => w.length > 2 && !STOP.has(w)) || []);
}

function highlighted(text, claim) {
  const keys = words(claim);
  return (text || "").split(/([\p{L}\p{N}]+)/u).map((p) => (keys.has(p.toLowerCase()) ? h("mark", null, p) : p));
}

export function sourcePanel(nguon, claim) {
  if (!nguon) return h("p", { class: "small muted" }, "Không có đoạn nguồn nào được trích cho câu này.");
  const where = [nguon.headingPath?.join(" › "), nguon.pages?.length ? `trang ${nguon.pages.join(", ")}` : null].filter(Boolean).join(" · ");
  return h("div", { class: "source" },
    h("div", { class: "source__head" }, h("span", null, where || "Tài liệu gốc"), h("code", null, nguon.id)),
    h("blockquote", { class: "source__text" }, highlighted(nguon.text, claim)));
}
