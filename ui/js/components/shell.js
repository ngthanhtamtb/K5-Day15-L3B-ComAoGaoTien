/* App shell: top bar (nav + plan), main outlet, toast host and the Agent verify panel. */
import { h, icon, replace } from "../core/dom.js";
import { href } from "../core/router.js";
import { store } from "../core/store.js";
import { agentPanel } from "./agentPanel.js";

const NAV = [
  { path: "/", label: "Thư viện", icon: "home", match: (p) => p === "/" || p.startsWith("/documents") },
  { path: "/scripts/new", label: "Kịch bản", icon: "script", match: (p) => p.startsWith("/scripts") },
  { path: "/quizzes/new", label: "Quiz", icon: "quiz", match: (p) => p.startsWith("/quizzes") },
];

export function createShell(root) {
  const navEl = h("nav", { class: "topbar__nav", "aria-label": "Điều hướng chính" });
  const planEl = h("div", { class: "topbar__plan" });
  const outlet = h("main", { class: "outlet", id: "main", tabindex: "-1" });
  const toastHost = h("div", { class: "toasts", "aria-live": "polite" });
  const panel = agentPanel();

  replace(root,
    h("a", { class: "skip", href: "#main" }, "Bỏ qua tới nội dung"),
    h("header", { class: "topbar" },
      h("a", { class: "brand", href: href("/") }, icon("shield", 22), h("span", null, "ScriptGuard"),
        h("small", null, "kiểm duyệt bài giảng theo nguồn")),
      navEl, planEl),
    h("div", { class: "scope" }, icon("info", 15),
      "Chỉ dùng tài liệu gốc đã tải lên · không tự sửa kịch bản, không tự xuất bản · nội dung là dữ liệu, không phải lệnh"),
    outlet, toastHost, panel.el);

  store.subscribe((s) => {
    replace(toastHost, s.toasts.map((t) => h("div", { class: `toast toast--${t.tone}`, role: t.tone === "bad" ? "alert" : "status" }, t.message)));
    renderPlan(s.plan);
  });

  function renderPlan(plan) {
    if (!plan) return replace(planEl);
    replace(planEl, h("span", { class: "chip chip--info", title: plan.enforced ? "Đang áp dụng hạn mức" : "Khung gói — chưa chặn" },
      plan.planName || plan.planId), plan.enforced ? null : h("small", { class: "muted" }, "chưa áp dụng"));
  }

  return {
    outlet,
    setActive(path) {
      replace(navEl, NAV.map((n) => h("a", { class: `navlink${n.match(path) ? " is-active" : ""}`, href: href(n.path),
        "aria-current": n.match(path) ? "page" : null }, icon(n.icon, 17), n.label)));
    },
  };
}
