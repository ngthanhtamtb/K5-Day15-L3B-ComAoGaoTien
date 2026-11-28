/* Lesson workspace: one place for a script and its slides + narration (two tabs).
 * No approval step — every segment is used unless dropped; fixes can happen at any time. */
import { scripts } from "../api/edu.js";
import { h, replace } from "../core/dom.js";
import { href } from "../core/router.js";
import { setTrace, toast } from "../core/store.js";
import { errorState, pageHead, skeleton } from "../components/ui.js";
import { scriptView } from "./lessonScript.js";
import { slidesView } from "./lessonSlides.js";

export function mount(el, { params, shell, tab = "script" }) {
  const ctx = { sc: null, listeners: new Set() };
  let view = null;
  let alive = true;
  replace(el, skeleton(6, 28));

  scripts.get(params.id).then((sc) => { ctx.sc = sc; draw(); })
    .catch((e) => replace(el, errorState(e, () => mount(el, { params, shell, tab }))));

  /** Apply a decision to one segment; drops get an Undo toast. Returns the updated script. */
  ctx.act = async (slide, seg, action, extra = {}) => {
    const res = await scripts.decide(ctx.sc.id, [{ slide, segment: seg.id, action, ...extra }]);
    if (action === "edit") setTrace(`Kiểm lại câu ${seg.id} (slide ${slide + 1}) sau khi sửa`, res.trace);
    ctx.set(res.data);
    if (action === "reject") {
      toast(`Đã bỏ câu ${seg.id} khỏi bài giảng`, "info", 7000, { label: "Hoàn tác",
        run: async () => ctx.set((await scripts.decide(ctx.sc.id, [{ slide, segment: seg.id, action: "reset" }])).data) });
    }
    return res.data;
  };
  ctx.set = (sc) => {
    ctx.sc = sc;
    if (alive) draw();
  };

  function draw() {
    const sc = ctx.sc;
    shell.setCrumbs([{ label: "Tài liệu", path: `/documents/${sc.docId}` }, { label: sc.title }], { wide: tab === "slides" });
    const segCount = sc.slides.reduce((n, s) => n + s.doan.length, 0);
    const need = sc.counts?.canXem || 0;
    const body = h("div");
    replace(el,
      pageHead({ eyebrow: "Bài giảng", title: sc.title,
        subtitle: `${sc.slides.length} slide · ${segCount} câu lời đọc${sc.origin === "generated" ? " · kịch bản do AI đề xuất từ tài liệu" : ""}` }),
      h("div", { class: "tabs", role: "tablist", "aria-label": "Phần của bài giảng" },
        tabLink("Slide & giọng đọc", `/scripts/${sc.id}/slides`, tab === "slides"),
        tabLink(sc.origin === "generated" ? "Kịch bản đề xuất" : "Kịch bản", `/scripts/${sc.id}`, tab === "script",
          need ? h("span", { class: "tag tag--warn" }, `${need} cần xem`) : null)),
      body);
    view?.destroy?.();
    view = (tab === "slides" ? slidesView : scriptView)(body, ctx);

  }

  return () => { alive = false; view?.destroy?.(); };
}

function tabLink(label, path, selected, extra) {
  return h("a", { class: "tab", role: "tab", href: href(path), "aria-selected": String(selected) }, label, extra);
}
