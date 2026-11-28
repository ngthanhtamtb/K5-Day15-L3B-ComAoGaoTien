/* Entry point: shell + router. Adding a screen = one line in ROUTES + one file in screens/.
 * Information architecture: Document → (Lesson workspace | Quiz). No approval step anywhere. */
import { system } from "./api/edu.js";
import { h, replace } from "./core/dom.js";
import { createRouter, go } from "./core/router.js";
import { store } from "./core/store.js";
import { createShell } from "./components/shell.js";
import { button, empty, skeleton } from "./components/ui.js";

const lesson = () => import("./screens/lesson.js");
const ROUTES = [
  { name: "home", path: "/", load: () => import("./screens/home.js"), title: "Tài liệu" },
  { name: "document", path: "/documents/:docId", load: () => import("./screens/document.js"), title: "Tài liệu" },
  { name: "slides", path: "/scripts/:id/slides", load: lesson, title: "Slide & giọng đọc", extra: { tab: "slides" } },
  { name: "script", path: "/scripts/:id", load: lesson, title: "Bài giảng", extra: { tab: "script" } },
  { name: "quiz", path: "/quizzes/:id", load: () => import("./screens/quiz.js"), title: "Quiz" },
  // old links: creation now opens in place on the document page
  { name: "legacyNew", path: "/scripts/new", redirect: (q) => (q.doc ? `/documents/${q.doc}?create=lesson` : "/") },
  { name: "legacyQuizNew", path: "/quizzes/new", redirect: (q) => (q.doc ? `/documents/${q.doc}?create=quiz` : "/") },
  { name: "notFound", path: "/__404__", load: null, title: "Không tìm thấy" },
];

const shell = createShell(document.getElementById("app"));
let cleanup = null;
let navToken = 0;

const router = createRouter(ROUTES, {
  async onChange({ route, params, query }) {
    if (route.redirect) return go(route.redirect(query));
    const token = ++navToken;
    if (typeof cleanup === "function") cleanup();
    cleanup = null;
    document.title = `${route.title} · ScriptGuard`;
    const outlet = shell.outlet;
    if (!route.load) {
      shell.setCrumbs([{ label: "Không tìm thấy" }]);
      return replace(outlet, empty("Trang này không tồn tại.", button("Về danh sách tài liệu", { kind: "primary", onClick: () => go("/") })));
    }
    replace(outlet, skeleton(4, 32));
    const mod = await route.load();
    if (token !== navToken) return;
    const view = h("div", { class: "screen" });
    replace(outlet, view);
    cleanup = mod.mount(view, { params, query, shell, ...(route.extra || {}) }) || null;
    outlet.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  },
});

router.start();
system.myPlan().then((plan) => store.set({ plan })).catch(() => {});
