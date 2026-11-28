/* Script tab — only what needs a decision is open:
 *   "Cần xem"  wrong / unsupported and not yet kept or dropped  (open)
 *   "Ổn"       matches the source or kept by the teacher         (folded, grouped by slide)
 *   "Đã loại"  dropped by the teacher or injected instruction    (folded, restorable)
 * One primary action: apply every suggested fix in one call, or move on to slides. */
import { scripts } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { go } from "../core/router.js";
import { setTrace, toast } from "../core/store.js";
import { claimLine, issueCard, unchecked } from "../components/claimCard.js";
import { busy, button, disclosure, healthBar } from "../components/ui.js";

export function classify(sc) {
  const need = [], fine = [], dropped = [];
  for (const s of sc.slides) {
    for (const g of s.doan) {
      const item = { slide: s.index, slideTitle: s.tieuDe, g };
      if (g.quyetDinh === "tu_choi_cau" || g.nhan === "TU_CHOI") dropped.push(item);
      else if ((g.nhan === "SAI_NGUON" || g.nhan === "THIEU_NGUON") && g.quyetDinh !== "chap_nhan") need.push(item);
      else fine.push(item);
    }
  }
  return { need, fine, dropped };
}

export function scriptView(el, ctx) {
  const sc = ctx.sc;
  const { need, fine, dropped } = classify(sc);
  const fixable = need.filter((x) => x.g.deXuatSua);
  const retry = need.filter((x) => unchecked(x.g));
  const where = (x) => ({ key: `${x.slide}-${x.g.id}`, label: `Slide ${x.slide + 1} · ${x.slideTitle} · ${x.g.id}`, short: x.g.id });
  const act = (x) => (action, extra) => ctx.act(x.slide, x.g, action, extra);

  const applyAll = button(`Áp dụng ${fixable.length} đề xuất sửa`, { kind: "primary", iconName: "check",
    onClick: async (e) => {
      const res = await busy(e.currentTarget, () => scripts.decide(sc.id,
        fixable.map((x) => ({ slide: x.slide, segment: x.g.id, action: "edit", text: x.g.deXuatSua }))));
      if (!res) return;
      setTrace(`Áp dụng ${fixable.length} đề xuất sửa và kiểm lại`, res.trace);
      toast(`Đã sửa ${fixable.length} câu theo đề xuất`, "ok");
      ctx.set(res.data);
    } });
  const retryAll = button(`Kiểm lại ${retry.length} câu`, { kind: "primary", iconName: "shield",
    onClick: async (e) => {
      const res = await busy(e.currentTarget, () => scripts.decide(sc.id,
        retry.map((x) => ({ slide: x.slide, segment: x.g.id, action: "edit", text: x.g.text }))));
      if (!res) return;
      setTrace(`Kiểm lại ${retry.length} câu bị lỗi gọi model`, res.trace);
      ctx.set(res.data);
    } });
  // exactly one primary: retry failed checks > apply suggestions > move on
  const primary = retry.length ? "retry" : fixable.length ? "fix" : "next";
  if (primary === "retry") applyAll.className = "btn";
  const next = button("Sang slide & giọng đọc", { kind: primary === "next" ? "primary" : "secondary", iconName: "arrowRight",
    onClick: () => go(`/scripts/${sc.id}/slides`) });

  replace(el, h("div", { class: "work-grid" },
    h("div", { class: "stack" },
      need.length
        ? h("section", { class: "stack" },
          h("div", { class: "section-title" }, h("h2", null, "Cần xem"), h("span", { class: "count" }, String(need.length))),
          h("p", { class: "small muted" }, "Câu sai hoặc không có trong tài liệu. Dùng đề xuất, sửa, giữ nguyên nếu bạn chắc chắn, hoặc bỏ câu."),
          need.map((x) => issueCard({ seg: x.g, where: where(x), act: act(x) })))
        : h("div", { class: "done-state" }, icon("check", 28), h("div", null, h("strong", null, "Không còn câu nào cần xem"),
          h("p", { class: "small muted" }, "Mọi câu đều khớp tài liệu hoặc đã được bạn xử lý."))),
      fine.length ? disclosure(h("span", { class: "row" }, "Ổn", h("span", { class: "count" }, String(fine.length))),
        bySlide(fine).map(([title, items]) => h("div", { class: "stack stack--sm" }, h("span", { class: "eyebrow" }, title),
          h("div", null, items.map((x) => claimLine({ seg: x.g, where: where(x), act: act(x), showTag: x.g.nhan !== "KHOP_NGUON" })))))) : null,
      dropped.length ? disclosure(h("span", { class: "row" }, "Đã loại", h("span", { class: "count" }, String(dropped.length))),
        dropped.map((x) => h("div", { class: "line" }, h("span", { class: "line__id" }, x.g.id),
          h("div", { class: "stack stack--sm" }, h("p", null, h("s", null, x.g.text)),
            h("span", { class: "small muted" }, x.g.nhan === "TU_CHOI"
              ? "Câu chứa chỉ dẫn gửi cho hệ thống — tự loại, không làm theo."
              : "Bạn đã bỏ câu này; nó không lên slide và giọng đọc.")),
          x.g.nhan === "TU_CHOI" ? h("span") : button("Khôi phục", { kind: "ghost", small: true, iconName: "undo",
            onClick: (e) => busy(e.currentTarget, () => ctx.act(x.slide, x.g, "reset")) })))) : null),
    h("aside", { class: "work-grid__side" },
      h("div", { class: "card" }, h("h2", null, "Đối chiếu với tài liệu"), healthBar(sc.counts?.nhan || {}),
        retry.length ? retryAll : null, fixable.length ? applyAll : null, next,
        h("p", { class: "small muted" }, "Mọi câu chưa bị bỏ đều được dùng cho slide và giọng đọc — không cần duyệt từng câu đúng.")))));
}

function bySlide(items) {
  const m = new Map();
  for (const x of items) {
    const k = `Slide ${x.slide + 1} · ${x.slideTitle}`;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(x);
  }
  return [...m.entries()];
}
