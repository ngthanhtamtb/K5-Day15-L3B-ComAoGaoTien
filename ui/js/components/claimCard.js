/* One narration segment, in two densities:
 *   issueCard(): full card for "Cần xem" — reason + suggestion visible, source behind a toggle
 *   claimLine(): compact row for "Ổn" / slide side panel — details and edit behind a toggle
 * Both edit in place; the caller's `act(action, extra)` talks to the API and re-renders. */
import { h, replace } from "../core/dom.js";
import { sourcePanel } from "./sourcePanel.js";
import { busy, button, disclosure, tag } from "./ui.js";

const TONE = { KHOP_NGUON: "ok", SAI_NGUON: "bad", THIEU_NGUON: "warn", TU_CHOI: "refuse", DAN_DAT: "muted" };

function editor(text, onSave, onCancel) {
  const ta = h("textarea", { class: "input", rows: 3, value: text, "aria-label": "Sửa câu (sẽ được kiểm lại với nguồn)" });
  const save = button("Lưu và kiểm lại", { kind: "primary", small: true,
    onClick: (e) => ta.value.trim() && busy(e.currentTarget, () => onSave(ta.value.trim())) });
  const form = h("div", { class: "stack stack--sm" }, ta,
    h("div", { class: "row" }, save, button("Huỷ", { kind: "ghost", small: true, onClick: onCancel })));
  queueMicrotask(() => { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); });
  return form;
}

export const unchecked = (seg) => /^Chưa kiểm được/.test(seg.lyDo || "");

export function issueCard({ seg, where, act }) {
  let editing = false;
  const el = h("article", { class: `issue issue--${TONE[seg.nhan] || "refuse"}`, id: `seg-${where.key}` });
  draw();
  return el;

  function draw() {
    replace(el,
      h("div", { class: "issue__meta" }, h("span", null, where.label), tag(seg.nhan)),
      editing ? editor(seg.text, async (text) => { await act("edit", { text }); }, () => { editing = false; draw(); })
        : h("p", { class: "issue__text" }, seg.text),
      seg.originalText && seg.originalText !== seg.text ? h("p", { class: "small" }, "Trước khi sửa: ", h("s", null, seg.originalText)) : null,
      seg.lyDo && !editing ? (unchecked(seg)
        ? h("div", { class: "stack stack--sm" }, h("p", { class: "issue__reason" }, "Chưa kiểm được vì lỗi kết nối model. Bấm “Kiểm lại”."),
          disclosure("Chi tiết kỹ thuật", h("p", { class: "small muted" }, seg.lyDo), { flat: true }))
        : h("p", { class: "issue__reason" }, seg.lyDo)) : null,
      seg.deXuatSua && !editing ? h("div", { class: "issue__fix" },
        h("span", { class: "issue__fix-label" }, "Đề xuất sửa theo nguồn"), h("p", null, seg.deXuatSua),
        h("div", null, button("Dùng đề xuất", { small: true, onClick: (e) => busy(e.currentTarget, () => act("edit", { text: seg.deXuatSua })) }))) : null,
      editing ? null : h("div", { class: "issue__actions" },
        unchecked(seg) ? button("Kiểm lại", { small: true, iconName: "shield", title: "Lần kiểm trước bị lỗi gọi model",
          onClick: (e) => busy(e.currentTarget, () => act("edit", { text: seg.text })) }) : null,
        button("Sửa", { kind: "ghost", small: true, iconName: "edit", onClick: () => { editing = true; draw(); } }),
        button("Giữ nguyên", { kind: "ghost", small: true, iconName: "check", title: "Câu đúng theo hiểu biết của bạn — không cần sửa",
          onClick: (e) => busy(e.currentTarget, () => act("accept")) }),
        button("Bỏ câu", { kind: "ghost", small: true, iconName: "x", onClick: (e) => busy(e.currentTarget, () => act("reject")) })),
      seg.nguon && !editing ? disclosure("Xem đoạn nguồn", sourcePanel(seg.nguon, seg.text), { flat: true }) : null);
  }
}

export function claimLine({ seg, where, act, showTag = false }) {
  let editing = false;
  const el = h("div", { class: "line", id: `seg-${where.key}` });
  draw();
  return el;

  function draw() {
    replace(el,
      h("span", { class: "line__id" }, where.short),
      h("div", { class: "stack stack--sm" },
        editing ? editor(seg.text, async (text) => { await act("edit", { text }); }, () => { editing = false; draw(); })
          : h("p", null, seg.text),
        showTag ? tag(seg.nhan) : null,
        editing ? null : disclosure("Chi tiết", h("div", { class: "stack stack--sm" },
          seg.lyDo && seg.nhan !== "KHOP_NGUON" ? h("p", { class: "small" }, seg.lyDo) : null,
          sourcePanel(seg.nguon, seg.text),
          h("div", { class: "issue__actions" },
            button("Sửa", { kind: "ghost", small: true, iconName: "edit", onClick: () => { editing = true; draw(); } }),
            button("Bỏ câu", { kind: "ghost", small: true, iconName: "x", onClick: (e) => busy(e.currentTarget, () => act("reject")) }))),
        { flat: true })),
      seg.voice ? h("span", { class: "small muted mono" }, `${Math.floor(seg.voice.start)}s`) : h("span"));
  }
}
