/* Hash router: "#/scripts/abc?tab=x" -> { name, params:{id:"abc"}, query:{tab:"x"} }.
 * Each route maps to a screen module exporting mount(el, ctx) -> optional cleanup(). */

export function createRouter(routes, { onChange } = {}) {
  const compiled = routes.map((r) => {
    const keys = [];
    const pattern = r.path.replace(/:([a-zA-Z]+)/g, (_, k) => { keys.push(k); return "([^/]+)"; });
    return { ...r, keys, re: new RegExp("^" + pattern + "/?$") };
  });

  function parse() {
    const raw = (location.hash || "#/").slice(1) || "/";
    const [path, qs = ""] = raw.split("?");
    const query = Object.fromEntries(new URLSearchParams(qs));
    for (const r of compiled) {
      const m = path.match(r.re);
      if (m) {
        const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
        return { route: r, params, query, path };
      }
    }
    return { route: compiled.find((r) => r.name === "notFound"), params: {}, query, path };
  }

  window.addEventListener("hashchange", () => onChange(parse()));
  return { start: () => onChange(parse()), parse };
}

export function go(path) {
  if (location.hash === "#" + path) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = path;
}

export function href(path) {
  return "#" + path;
}
