/* DOM helpers. Every string coming from the API is inserted as a text node — there is no
 * innerHTML anywhere in the UI (content is teacher/document data and may contain markup). */

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2).toLowerCase(), value);
      else if (key === "value") el.value = value;
      else if (key === "checked" || key === "disabled" || key === "selected") el[key] = Boolean(value);
      else if (value === true) el.setAttribute(key, "");
      else el.setAttribute(key, String(value));
    }
  }
  append(el, children);
  return el;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === true) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

export function replace(el, ...children) {
  clear(el);
  return append(el, children);
}

/* ---- icons: fixed path data (trusted constants, never API data) ---- */
const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS = {
  doc: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5", "M9 13h6", "M9 17h6"],
  upload: ["M12 16V4", "M7 9l5-5 5 5", "M4 20h16"],
  check: ["M5 12l5 5L20 7"],
  x: ["M6 6l12 12", "M18 6L6 18"],
  edit: ["M4 20h4L19 9l-4-4L4 16z", "M13 7l4 4"],
  undo: ["M9 14L4 9l5-5", "M4 9h11a5 5 0 0 1 0 10h-3"],
  play: ["M7 5v14l12-7z"],
  pause: ["M8 5v14", "M16 5v14"],
  slides: ["M3 5h18v12H3z", "M8 21h8", "M12 17v4"],
  quiz: ["M9 9a3 3 0 1 1 4 2.8c-.6.3-1 .9-1 1.6V14", "M12 18h.01", "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z"],
  script: ["M4 6h16", "M4 12h16", "M4 18h10"],
  shield: ["M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z", "M9 12l2 2 4-4"],
  mic: ["M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z", "M5 11a7 7 0 0 0 14 0", "M12 18v3"],
  arrowLeft: ["M15 6l-6 6 6 6"],
  arrowRight: ["M9 6l6 6-6 6"],
  download: ["M12 4v12", "M7 11l5 5 5-5", "M4 20h16"],
  image: ["M4 5h16v14H4z", "M4 15l4-4 4 4 3-3 5 5", "M15 9h.01"],
  table: ["M4 5h16v14H4z", "M4 10h16", "M4 15h16", "M10 5v14"],
  home: ["M4 11l8-7 8 7", "M6 9v11h12V9"],
  spark: ["M12 3v4", "M12 17v4", "M3 12h4", "M17 12h4", "M6 6l2.5 2.5", "M15.5 15.5L18 18", "M6 18l2.5-2.5", "M15.5 8.5L18 6"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 11v6", "M12 7h.01"],
};

export function icon(name, size = 18) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const d of ICONS[name] || ICONS.info) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d);
    svg.append(p);
  }
  return svg;
}

export function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) el.setAttribute(k, String(v));
  return el;
}

/** Plain text of an HTML fragment WITHOUT inserting it into the page (inert parser, no scripts run). */
export function htmlToText(html) {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(String(html), "text/html");
  return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
}
