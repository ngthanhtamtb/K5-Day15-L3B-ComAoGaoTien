/* Home: upload a source document, then jump into a script or a quiz. Lists past work. */
import { documents, jobs, quizzes, scripts } from "../api/edu.js";
import { h, icon, replace } from "../core/dom.js";
import { fmtDate } from "../core/format.js";
import { go, href } from "../core/router.js";
import { toast } from "../core/store.js";
import { button, card, empty, errorBox, pageHeader, progressBar, spinner } from "../components/ui.js";

const ACCEPT = ".pdf,.docx,.pptx,.md,.txt,.doc,.ppt";

export function mount(el) {
  const uploadArea = h("div");
  const docsBox = h("div", null, spinner());
  const scriptsBox = h("div", null, spinner());
  const quizBox = h("div", null, spinner());

  replace(el,
    pageHeader("Thư viện", "Tải tài liệu gốc của buổi học, rồi tạo kịch bản thuyết trình hoặc bộ quiz có đối chiếu nguồn."),
    uploadArea,
    h("div", { class: "grid grid--3" },
      card("Tài liệu gốc", docsBox), card("Kịch bản", scriptsBox), card("Quiz", quizBox)));

  renderUpload();
  load();

  function renderUpload(state = {}) {
    const input = h("input", { type: "file", accept: ACCEPT, class: "visually-hidden", id: "upload-input",
      onChange: (e) => e.target.files[0] && upload(e.target.files[0]) });
    const drop = h("label", { class: `dropzone${state.drag ? " is-drag" : ""}`, for: "upload-input" },
      icon("upload", 26),
      h("strong", null, "Kéo thả hoặc chọn tài liệu gốc"),
      h("span", { class: "muted small" }, "PDF, DOCX, PPTX, MD, TXT · đọc tại máy: giữ ảnh, bảng, vị trí và ghi chú người nói"),
      input);
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("is-drag"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("is-drag"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("is-drag");
      if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    });
    replace(uploadArea, state.progress ? card(null, progressBar(state.progress.pct, state.progress.label)) : drop);
  }

  async function upload(file) {
    renderUpload({ progress: { pct: 5, label: `Đang tải ${file.name}…` } });
    try {
      let docId;
      if (/\.(pdf|pptx?)$/i.test(file.name)) {        // large files: background job with progress
        const { jobId } = await documents.uploadAsync(file);
        const snap = await jobs.wait(jobId, (s) => renderUpload({ progress: { pct: s.progress_pct, label: s.message || "Đang xử lý…" } }));
        if (snap.status !== "done") throw new Error(snap.error || "Xử lý tài liệu thất bại");
        docId = snap.result.docId;
      } else {
        docId = (await documents.upload(file)).docId;
      }
      toast(`Đã đọc xong ${file.name}`, "ok");
      go(`/documents/${docId}`);
    } catch (e) {
      toast(e.message, "bad", 8000);
      renderUpload();
    }
  }

  async function load() {
    const [d, s, q] = await Promise.allSettled([documents.list(), scripts.list(), quizzes.list()]);
    replace(docsBox, d.status === "fulfilled" ? docList(d.value) : errorBox(d.reason, load));
    replace(scriptsBox, s.status === "fulfilled" ? scriptList(s.value) : errorBox(s.reason, load));
    replace(quizBox, q.status === "fulfilled" ? quizList(q.value) : errorBox(q.reason, load));
  }
}

function docList(items) {
  if (!items.length) return empty("Chưa có tài liệu nào.");
  return h("ul", { class: "list" }, items.map((d) => h("li", { class: "list__item" },
    h("a", { class: "list__main", href: href(`/documents/${d.docId}`) }, icon("doc", 16), h("span", null, d.filename)),
    h("span", { class: "muted small" }, [d.stats?.pages ? `${d.stats.pages} trang` : null, `${d.stats?.images || 0} hình`,
      `${d.stats?.tables || 0} bảng`].filter(Boolean).join(" · ")))));
}

function scriptList(items) {
  if (!items.length) return empty("Chưa có kịch bản.", button("Tạo kịch bản", { onClick: () => go("/scripts/new"), small: true }));
  return h("ul", { class: "list" }, items.map((s) => h("li", { class: "list__item" },
    h("a", { class: "list__main", href: href(`/scripts/${s.id}`) }, icon("script", 16), h("span", null, s.title)),
    h("span", { class: `chip ${s.status === "cho_duyet" ? "chip--ok" : "chip--muted"}` }, s.status === "cho_duyet" ? "Chờ duyệt" : "Đang rà soát"),
    h("span", { class: "muted small" }, fmtDate(s.updatedAt)))));
}

function quizList(items) {
  if (!items.length) return empty("Chưa có quiz.", button("Tạo quiz", { onClick: () => go("/quizzes/new"), small: true }));
  return h("ul", { class: "list" }, items.map((q) => h("li", { class: "list__item" },
    h("a", { class: "list__main", href: href(`/quizzes/${q.id}`) }, icon("quiz", 16), h("span", null, q.title)),
    h("span", { class: `chip ${q.status === "cho_duyet" ? "chip--ok" : "chip--muted"}` }, `${q.decided}/${q.questions} câu`),
    h("span", { class: "muted small" }, fmtDate(q.updatedAt)))));
}
