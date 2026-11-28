/* App shell: one quiet top bar (brand + breadcrumbs), the outlet, toasts and the Agent panel.
 * No global nav menu: everything starts from a document, so breadcrumbs are enough. */
import { h, icon, replace } from "../core/dom.js";
import { href } from "../core/router.js";
import { store } from "../core/store.js";
import { agentPanel } from "./agentPanel.js";

export function createShell(root) {
  const crumbsEl = h("nav", { class: "crumbs", "aria-label": "Vị trí" });
  const planEl = h("div", { class: "row", style: { marginLeft: "auto" } });
  const outlet = h("main", { class: "outlet", id: "main", tabindex: "-1" });
  const toastHost = h("div", { class: "toasts", "aria-live": "polite" });
  const panel = agentPanel();

  replace(root,
    h("a", { class: "skip", href: "#main" }, "Bỏ qua tới nội dung"),
    h("header", { class: "topbar" },
      h("a", { class: "brand", href: href("/"), "aria-label": "ScriptGuard — về trang chính" }, icon("shield", 22), "ScriptGuard"),
      crumbsEl, planEl),
    outlet, toastHost, panel.el);

  store.subscribe((s) => {
    replace(toastHost, s.toasts.map((t) => h("div", { class: `toast${t.tone === "bad" ? " toast--bad" : ""}`, role: t.tone === "bad" ? "alert" : "status" },
      h("span", null, t.message),
      t.action ? h("button", { class: "link-btn", type: "button", onClick: () => { t.dismiss(); t.action.run(); } }, t.action.label) : null)));
    // plans are a framework only: show them when limits are actually enforced
    replace(planEl, s.plan?.enforced ? h("span", { class: "pill" }, s.plan.planName || s.plan.planId) : null);
  });

  return {
    outlet,
    /** crumbs: [{label, path?}] — the last one is the current page */
    setCrumbs(crumbs = [], { wide = false } = {}) {
      outlet.classList.toggle("outlet--wide", wide);
      replace(crumbsEl, crumbs.flatMap((c, i) => [
        h("span", { "aria-hidden": "true" }, "/"),
        i < crumbs.length - 1 && c.path ? h("a", { href: href(c.path) }, c.label) : h("span", { "aria-current": "page" }, c.label),
      ]));
    },
  };
}
