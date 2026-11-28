/* Entry point: shell + router. Adding a screen = one line in ROUTES + one file in screens/. */
import { system } from "./api/edu.js";
import { h, replace } from "./core/dom.js";
import { createRouter, go } from "./core/router.js";
import { store } from "./core/store.js";
import { createShell } from "./components/shell.js";
import { button, empty, spinner } from "./components/ui.js";

const ROUTES = [
  { name: "library", path: "/", load: () => import("./screens/library.js"), title: "Thư viện" },
  { name: "document", path: "/documents/:docId", load: () => import("./screens/document.js"), title: "Tài liệu" },
  { name: "scriptNew", path: "/scripts/new", load: () => import("./screens/scriptNew.js"), title: "Tạo kịch bản" },
  { name: "slides", path: "/scripts/:id/slides", load: () => import("./screens/slideStudio.js"), title: "Slide & giọng đọc" },
  { name: "script", path: "/scripts/:id", load: () => import("./screens/scriptReview.js"), title: "Rà soát kịch bản" },
  { name: "quizNew", path: "/quizzes/new", load: () => import("./screens/quizNew.js"), title: "Tạo quiz" },
  { name: "quiz", path: "/quizzes/:id", load: () => import("./screens/quizReview.js"), title: "Kiểm quiz" },
  { name: "notFound", path: "/__404__", load: null, title: "Không tìm thấy" },
];

const shell = createShell(document.getElementById("app"));
let cleanup = null;
let navToken = 0;

const router = createRouter(ROUTES, {
  async onChange({ route, params, query, path }) {
    const token = ++navToken;
    if (typeof cleanup === "function") cleanup();
    cleanup = null;
    shell.setActive(path);
    document.title = `${route.title} · ScriptGuard`;
    const outlet = shell.outlet;
    if (!route.load) {
      replace(outlet, empty("Trang không tồn tại.", button("Về thư viện", { kind: "primary", onClick: () => go("/") })));
      return;
    }
    replace(outlet, spinner());
    const mod = await route.load();
    if (token !== navToken) return;                 // user navigated again while loading
    const view = h("div", { class: "screen" });
    replace(outlet, view);
    cleanup = mod.mount(view, { params, query }) || null;
    outlet.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  },
});

router.start();
system.myPlan().then((plan) => store.set({ plan })).catch(() => {});
