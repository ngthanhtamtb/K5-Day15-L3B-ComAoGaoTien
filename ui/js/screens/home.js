/* Home — document-centred. First run: one big drop zone. Afterwards: each document with the
 * lessons and quizzes made from it, and how many items still need a look. */
import { documents, jobs, quizzes, scripts } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { go, href } from "../core/router.js";
import { toast } from "../core/store.js";
import { busy, button, errorState, pageHead, progress, skeleton } from "../components/ui.js";

const ACCEPT = ".pdf,.docx,.pptx,.md,.txt,.doc,.ppt";

export function mount(el, { shell }) {
  shell.setCrumbs([]);
  replace(el, skeleton(4, 56));
  load();

  async function load() {
    try {
      const [docs, scs, qzs] = await Promise.all([documents.list(), scripts.list(), quizzes.list()]);
      render(docs, scs, qzs);
    } catch (e) {
      replace(el, errorState(e, load));
    }
  }

  function render(docs, scs, qzs) {
    if (!docs.length) return replace(el, firstRun());
    const uploadBtn = uploader({ compact: true });
    replace(el,
      pageHead({ title: "Tài liệu", subtitle: "Chọn một tài liệu để tạo bài giảng có giọng đọc hoặc bộ quiz — mọi câu được đối chiếu với chính tài liệu đó.",
        actions: uploadBtn }),
      h("div", { class: "doclist" }, docs.map((d) => docRow(d, scs.filter((s) => s.docId === d.docId), qzs.filter((q) => q.docId === d.docId)))));
  }

  function firstRun() {
    return h("section", { class: "hero" },
      h("h1", null, "Bắt đầu từ tài liệu gốc của buổi học"),
      h("p", null, "ScriptGuard đọc tài liệu ngay trên máy chủ của bạn (giữ hình, bảng và ghi chú người nói), rồi kiểm từng câu kịch bản và từng câu hỏi với chính tài liệu đó."),
      uploader({ compact: false }));
  }

  function uploader({ compact }) {
    const input = h("input", { type: "file", accept: ACCEPT, class: "visually-hidden", id: "upload",
      onChange: (e) => e.target.files[0] && upload(e.target.files[0], wrap) });
    const wrap = h("div");
    if (compact) {
      replace(wrap, h("label", { class: "btn btn--primary", for: "upload" }, icon("upload", 18), "Tải tài liệu"), input);
    } else {
      const zone = h("label", { class: "drop", for: "upload" }, icon("upload", 28),
        h("strong", null, "Kéo thả hoặc chọn tài liệu"),
        h("span", { class: "small muted" }, "PDF, DOCX, PPTX, MD, TXT"), input);
      zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("is-drag"); });
      zone.addEventListener("dragleave", () => zone.classList.remove("is-drag"));
      zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("is-drag"); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0], wrap); });
      replace(wrap, zone);
      wrap.style.width = "100%";
      wrap.style.display = "flex";
      wrap.style.justifyContent = "center";
    }
    return wrap;
  }

  async function upload(file, slot) {
    const show = (pct, label) => replace(slot, h("div", { style: { minWidth: "280px" } }, progress(pct, label)));
    show(5, `Đang tải ${file.name}`);
    try {
      let docId;
      if (/\.(pdf|pptx?)$/i.test(file.name)) {
        const { jobId } = await documents.uploadAsync(file);
        const snap = await jobs.wait(jobId, (s) => show(s.progress_pct, s.message || "Đang đọc tài liệu"));
        if (snap.status !== "done") throw new Error(snap.error || "Không đọc được tài liệu");
        docId = snap.result.docId;
      } else {
        docId = (await documents.upload(file)).docId;
      }
      go(`/documents/${docId}`);
    } catch (e) {
      toast(e.message, "bad", 8000);
      load();
    }
  }
}

function docRow(d, scs, qzs) {
  const s = d.stats || {};
  const meta = [s.pages ? `${s.pages} trang` : null, `${s.chunks} đoạn`, s.images ? `${s.images} hình` : null, s.tables ? `${s.tables} bảng` : null].filter(Boolean);
  const work = [
    ...scs.map((x) => workChip(`/scripts/${x.id}`, "script", x.title, x.needsReview)),
    ...qzs.map((x) => workChip(`/quizzes/${x.id}`, "quiz", x.title, x.needsReview)),
  ];
  return h("div", { class: "docrow" },
    h("a", { class: "docrow__name", href: href(`/documents/${d.docId}`) }, icon("doc", 18), h("span", null, d.filename)),
    h("a", { class: "btn btn--ghost btn--sm", href: href(`/documents/${d.docId}?create=lesson`) }, "Tạo bài giảng"),
    h("div", { class: "docrow__meta" }, meta.join(" · ")),
    work.length ? h("div", { class: "docrow__work" }, work) : null);
}

function workChip(path, kind, title, needs) {
  return h("a", { class: "work", href: href(path) }, icon(kind, 15), h("span", null, title),
    needs ? h("span", { class: "tag tag--warn" }, `${needs} cần xem`) : h("span", { class: "tag tag--ok" }, "ổn"));
}
