/* Screen 2 · Gate 1: label filter + progress, segment list grouped by slide, detail panel with
 * reason, suggestion and cited source; accept / reject / edit (re-checked) / reset. */
import { scripts } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { go } from "../core/router.js";
import { setTrace } from "../core/store.js";
import { sourcePanel } from "../components/sourcePanel.js";
import { badge, busy, button, decisionChip, errorBox, LABELS, pageHeader, progressBar, spinner, stepper } from "../components/ui.js";
import { SCRIPT_STEPS } from "./scriptNew.js";

export function mount(el, { params }) {
  const st = { sc: null, filter: "ALL", sel: null, editing: false };
  replace(el, spinner("Đang mở kịch bản…"));
  scripts.get(params.id).then((sc) => { st.sc = sc; st.sel = firstPending(sc); render(); })
    .catch((e) => replace(el, errorBox(e, () => mount(el, { params }))));

  const onKey = (e) => {
    if (!st.sc || st.editing || /input|textarea|select/i.test(e.target.tagName)) return;
    if (e.key === "j" || e.key === "ArrowDown") move(1);
    if (e.key === "k" || e.key === "ArrowUp") move(-1);
  };
  document.addEventListener("keydown", onKey);

  function flat() {
    return st.sc.slides.flatMap((s) => s.doan.map((g) => ({ slide: s.index, slideTitle: s.tieuDe, g })));
  }
  function visible() {
    return flat().filter((x) => st.filter === "ALL" || x.g.nhan === st.filter);
  }
  function current() {
    return flat().find((x) => st.sel && x.slide === st.sel.slide && x.g.id === st.sel.seg) || visible()[0];
  }
  function move(d) {
    const list = visible();
    const i = list.findIndex((x) => x === current() || (x.slide === current()?.slide && x.g.id === current()?.g.id));
    const next = list[Math.max(0, Math.min(list.length - 1, i + d))];
    if (next) { st.sel = { slide: next.slide, seg: next.g.id }; render(); }
  }

  function render() {
    const sc = st.sc;
    const all = flat();
    const decided = all.filter((x) => x.g.quyetDinh !== "chua_quyet").length;
    const locked = sc.status !== "nhap";
    const matchingPending = all.filter((x) => x.g.nhan === "KHOP_NGUON" && x.g.quyetDinh === "chua_quyet").length;
    const counts = sc.counts?.nhan || {};

    const submitBtn = button(locked ? "Đã gửi chờ duyệt" : "Gửi chờ duyệt", {
      kind: "primary", iconName: "check", disabled: locked || decided < all.length,
      title: decided < all.length ? "Còn câu chưa quyết định" : null,
      onClick: (e) => act(e.currentTarget, () => scripts.submit(sc.id), "Đã gửi chờ duyệt"),
    });
    const bulkBtn = button(`Chấp nhận mọi câu “Khớp nguồn” chưa quyết (${matchingPending})`, {
      disabled: locked || !matchingPending, small: true,
      onClick: (e) => act(e.currentTarget, () => scripts.acceptMatching(sc.id)),
    });

    replace(el,
      stepper(SCRIPT_STEPS, locked ? 2 : 1),
      pageHeader(`Rà soát kịch bản: ${sc.title}`, `${sc.origin === "generated" ? "Sinh từ tài liệu" : "Bản nháp dán vào"} · ${all.length} đoạn lời đọc`,
        [locked ? button("Tạo slide & giọng đọc", { kind: "primary", iconName: "slides", onClick: () => go(`/scripts/${sc.id}/slides`) }) : null, submitBtn]),
      locked ? h("div", { class: "alert alert--ok" }, icon("check", 16),
        "Kịch bản đã qua cổng 1 và ở trạng thái chờ duyệt. Sửa tiếp ở màn slide (cổng 2).") : null,
      h("div", { class: "toolbar" },
        h("div", { class: "filters", role: "tablist", "aria-label": "Lọc theo nhãn" },
          filterBtn("ALL", "Tất cả", all.length),
          Object.keys(LABELS).map((k) => filterBtn(k, LABELS[k].text.split(" /")[0], counts[k] || 0))),
        h("div", { class: "toolbar__right" }, progressBar(all.length ? (decided / all.length) * 100 : 0, `Đã quyết định ${decided}/${all.length}`), bulkBtn)),
      h("div", { class: "split" }, listView(), detailView(locked)));
  }

  function filterBtn(key, label, n) {
    return h("button", { class: `filter${st.filter === key ? " is-active" : ""}`, type: "button", role: "tab",
      "aria-selected": String(st.filter === key), onClick: () => { st.filter = key; render(); } }, label, h("span", { class: "filter__n" }, String(n)));
  }

  function listView() {
    const cur = current();
    const groups = new Map();
    for (const x of visible()) {
      if (!groups.has(x.slide)) groups.set(x.slide, []);
      groups.get(x.slide).push(x);
    }
    if (!groups.size) return h("div", { class: "split__list" }, h("p", { class: "muted" }, "Không có câu nào với nhãn này."));
    return h("div", { class: "split__list", role: "listbox", "aria-label": "Các đoạn lời đọc" },
      [...groups.entries()].map(([slide, items]) => h("div", { class: "group" },
        h("div", { class: "group__title" }, `Slide ${slide + 1} · ${items[0].slideTitle}`),
        items.map((x) => h("button", {
          class: `claim${cur && cur.slide === x.slide && cur.g.id === x.g.id ? " is-selected" : ""}`, type: "button", role: "option",
          "aria-selected": String(cur && cur.slide === x.slide && cur.g.id === x.g.id),
          onClick: () => { st.sel = { slide: x.slide, seg: x.g.id }; st.editing = false; render(); },
        }, h("span", { class: "claim__id mono" }, x.g.id), h("span", { class: "claim__text" }, x.g.text),
        h("span", { class: "claim__meta" }, badge(x.g.nhan, { short: true }), decisionChip(x.g.quyetDinh)))))));
  }

  function detailView(locked) {
    const x = current();
    if (!x) return h("div", { class: "split__detail" });
    const g = x.g;
    const textarea = h("textarea", { class: "input textarea", rows: 4, id: "edit-text", value: g.text });
    const decide = (action, extra = {}) => (e) => act(e.currentTarget,
      async () => {
        const res = await scripts.decide(st.sc.id, [{ slide: x.slide, segment: g.id, action, ...extra }]);
        if (action === "edit") setTrace(`Kiểm lại đoạn ${g.id} sau khi sửa`, res.trace);
        st.editing = false;
        return res.data;
      }, null, action === "accept" || action === "reject");

    return h("div", { class: "split__detail", "aria-live": "polite" },
      h("div", { class: "row row--between" },
        h("span", { class: "muted small" }, `Slide ${x.slide + 1} · đoạn ${g.id}`),
        h("div", { class: "row" }, button(null, { iconName: "arrowLeft", small: true, onClick: () => move(-1), title: "Câu trước (k)" }),
          button(null, { iconName: "arrowRight", small: true, onClick: () => move(1), title: "Câu tiếp (j)" }))),
      h("div", { class: "detail__label" }, badge(g.nhan), decisionChip(g.quyetDinh)),
      h("p", { class: "detail__text" }, g.text),
      g.originalText && g.originalText !== g.text ? h("p", { class: "muted small" }, "Bản gốc: ", h("s", null, g.originalText)) : null,
      g.lyDo ? h("div", { class: "detail__block" }, h("h3", null, "Lý do gắn nhãn"), h("p", null, g.lyDo)) : null,
      g.canhBaoMa ? h("div", { class: "alert alert--warn small" }, "Mã nguồn ghi sẵn không khớp: ", g.canhBaoMa) : null,
      g.deXuatSua ? h("div", { class: "detail__block detail__block--fix" }, h("h3", null, "Đề xuất sửa (giảng viên quyết định)"),
        h("p", null, g.deXuatSua),
        !locked ? button("Dùng đề xuất này", { small: true, iconName: "edit", onClick: decide("edit", { text: g.deXuatSua }) }) : null) : null,
      sourcePanel(g.nguon, g.text),
      locked ? null : st.editing
        ? h("div", { class: "stack" }, h("label", { class: "field__label", for: "edit-text" }, "Sửa đoạn (sẽ được kiểm lại ngay)"), textarea,
          h("div", { class: "row" },
            button("Lưu & kiểm lại", { kind: "primary", onClick: (e) => textarea.value.trim() && decide("edit", { text: textarea.value.trim() })(e) }),
            button("Huỷ", { onClick: () => { st.editing = false; render(); } })))
        : h("div", { class: "actions" },
          button("Chấp nhận nhãn", { kind: "primary", iconName: "check", disabled: g.nhan === "TU_CHOI",
            title: g.nhan === "TU_CHOI" ? "Đoạn chứa chỉ dẫn chèn không thể chấp nhận" : null, onClick: decide("accept") }),
          button("Từ chối câu", { iconName: "x", onClick: decide("reject") }),
          g.nhan !== "TU_CHOI" ? button("Sửa", { iconName: "edit", onClick: () => { st.editing = true; render(); textarea.focus(); } }) : null,
          g.quyetDinh !== "chua_quyet" ? button("Bỏ quyết định", { iconName: "undo", onClick: decide("reset") }) : null));
  }

  async function act(btn, fn, ok, advance = false) {
    const sc = await busy(btn, fn, { ok });
    if (!sc) return;
    st.sc = sc;
    if (advance) {
      const next = firstPending(sc, st.sel);
      if (next) st.sel = next;
    }
    render();
  }

  return () => document.removeEventListener("keydown", onKey);
}

function firstPending(sc, after) {
  const all = sc.slides.flatMap((s) => s.doan.map((g) => ({ slide: s.index, seg: g.id, g })));
  const start = after ? all.findIndex((x) => x.slide === after.slide && x.seg === after.seg) + 1 : 0;
  const hit = [...all.slice(start), ...all.slice(0, start)].find((x) => x.g.quyetDinh === "chua_quyet");
  return hit ? { slide: hit.slide, seg: hit.seg } : all[0] ? { slide: all[0].slide, seg: all[0].seg } : null;
}
