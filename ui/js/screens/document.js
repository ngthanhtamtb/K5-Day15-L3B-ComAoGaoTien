/* What the parser extracted from one document: chunks (citable units), figures, tables. */
import { documents } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { go } from "../core/router.js";
import { button, card, empty, errorBox, pageHeader, spinner, stat } from "../components/ui.js";

export function mount(el, { params }) {
  replace(el, spinner("Đang mở tài liệu…"));
  let tab = "chunks";
  let doc;

  documents.get(params.docId, false).then((d) => { doc = d; render(); })
    .catch((e) => replace(el, errorBox(e, () => mount(el, { params }))));

  function render() {
    const images = Object.values(doc.images || {});
    const tables = Object.values(doc.tables || {});
    const tabs = [["chunks", `Đoạn nguồn (${doc.chunks.length})`], ["images", `Hình (${images.length})`], ["tables", `Bảng (${tables.length})`]];
    replace(el,
      pageHeader(doc.filename, `Bộ đọc: ${doc.engine}`, [
        button("Tạo kịch bản", { kind: "primary", iconName: "script", onClick: () => go(`/scripts/new?doc=${doc.doc_id}`) }),
        button("Tạo quiz", { iconName: "quiz", onClick: () => go(`/quizzes/new?doc=${doc.doc_id}`) }),
      ]),
      h("div", { class: "stats" },
        stat("Trang / slide", doc.meta?.pages ?? doc.meta?.slides ?? "—"), stat("Đoạn nguồn", doc.chunks.length),
        stat("Hình", images.length), stat("Bảng", tables.length),
        doc.meta?.ocr_pages?.length ? stat("Trang đã OCR", doc.meta.ocr_pages.length) : null,
        doc.meta?.scan_pages_without_ocr?.length ? stat("Trang scan chưa OCR", doc.meta.scan_pages_without_ocr.length) : null),
      h("div", { class: "tabs", role: "tablist" }, tabs.map(([k, label]) => h("button", {
        class: `tab${tab === k ? " is-active" : ""}`, role: "tab", "aria-selected": String(tab === k), type: "button",
        onClick: () => { tab = k; render(); } }, label))),
      tab === "chunks" ? chunks(doc) : tab === "images" ? gallery(images) : tableList(tables));
  }
}

function chunks(doc) {
  if (!doc.chunks.length) return empty("Không tách được đoạn nào.");
  return h("div", { class: "stack" }, doc.chunks.map((c) => card(null,
    h("div", { class: "row row--between" }, h("code", null, c.id),
      h("span", { class: "muted small" }, [c.headingPath?.join?.(" › ") || c.heading_path?.join(" › "),
        c.pages?.length ? `trang ${c.pages.join(", ")}` : null].filter(Boolean).join(" · "))),
    h("p", { class: "prewrap" }, c.text))));
}

function gallery(images) {
  if (!images.length) return empty("Tài liệu không có hình (hoặc hình nhỏ hơn ngưỡng lọc).");
  return h("div", { class: "gallery" }, images.map((img) => h("figure", { class: "gallery__item" },
    h("img", { src: img.url, alt: img.alt || img.caption || img.id, loading: "lazy" }),
    h("figcaption", null, h("code", null, img.id), img.page ? ` · trang ${img.page}` : "",
      img.alt ? h("div", null, img.alt) : null, img.caption ? h("div", { class: "muted small" }, img.caption) : null))));
}

function tableList(tables) {
  if (!tables.length) return empty("Tài liệu không có bảng.");
  return h("div", { class: "stack" }, tables.map((t) => {
    const rows = [];
    for (const c of t.cells) (rows[c.row] ||= [])[c.col] = c.text;
    return card(null, h("div", { class: "row row--between" }, h("span", null, icon("table", 16), h("code", null, t.id)),
      h("span", { class: "muted small" }, `${t.n_rows} × ${t.n_cols}`)),
    h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("tbody", null, rows.map((r, i) => h("tr", null, (r || []).map((cell) => h(i === 0 ? "th" : "td", null, cell ?? ""))))))));
  }));
}
