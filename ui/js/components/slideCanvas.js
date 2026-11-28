/* Read-only renderer for PPTist slide JSON (shapes, text, images, lines) scaled to its box.
 * Text content arrives as HTML from the template engine: it is converted to plain text with an
 * inert parser and inserted as text — no markup from the API reaches the page. */
import { h, htmlToText, svgEl } from "../core/dom.js";

function fontSize(html, fallback = 16) {
  const m = /font-size:\s*(\d+(?:\.\d+)?)px/i.exec(html || "");
  return m ? Number(m[1]) : fallback;
}

function color(html) {
  const m = /(?:^|[;\s"])color:\s*(#[0-9a-f]{3,8}|rgba?\([^)]*\))/i.exec(html || "");
  return m ? m[1] : null;
}

function box(el) {
  return { left: `${el.left || 0}px`, top: `${el.top || 0}px`, width: `${el.width || 0}px`, height: `${el.height || 0}px`,
    transform: el.rotate ? `rotate(${el.rotate}deg)` : null };
}

function textNode(html, defaultColor) {
  const text = htmlToText(html);
  if (!text) return null;
  return h("div", { class: "pp-text", style: { fontSize: `${fontSize(html)}px`, color: color(html) || defaultColor || null } }, text);
}

function shape(el) {
  const [vw, vh] = el.viewBox || [el.width, el.height];
  const svg = svgEl("svg", { viewBox: `0 0 ${vw} ${vh}`, width: "100%", height: "100%", preserveAspectRatio: "none" });
  if (el.path) {
    svg.append(svgEl("path", { d: el.path, fill: el.fill || "none", stroke: el.outline?.color || "none",
      "stroke-width": el.outline?.width || 0, opacity: el.opacity ?? 1 }));
  }
  const wrap = h("div", { class: "pp-el", style: { ...box(el), transform: [box(el).transform, el.flipH ? "scaleX(-1)" : "", el.flipV ? "scaleY(-1)" : ""].filter(Boolean).join(" ") || null } });
  wrap.append(svg);
  const t = el.text?.content ? textNode(el.text.content, el.text.defaultColor) : null;
  if (t) wrap.append(h("div", { class: "pp-shape-text", style: { transform: [el.flipH ? "scaleX(-1)" : "", el.flipV ? "scaleY(-1)" : ""].join(" ") || null } }, t));
  return wrap;
}

function line(el) {
  const [x1, y1] = el.start || [0, 0];
  const [x2, y2] = el.end || [el.width || 0, 0];
  const w = Math.max(Math.abs(x2 - x1), 1);
  const hgt = Math.max(Math.abs(y2 - y1), 1);
  const svg = svgEl("svg", { width: w, height: hgt, style: "overflow:visible" });
  svg.append(svgEl("line", { x1, y1, x2, y2, stroke: el.color || "#333", "stroke-width": el.width || 2 }));
  return h("div", { class: "pp-el", style: { left: `${el.left || 0}px`, top: `${el.top || 0}px` } }, svg);
}

export function slideCanvas(slide, { width = 1000, height = 562.5, highlight, thumb = false } = {}) {
  const stage = h("div", { class: "pp-stage", style: { width: `${width}px`, height: `${height}px` } });
  const bg = slide.background || {};
  if (bg.type === "solid" && bg.color) stage.style.background = bg.color;
  if (bg.type === "image" && bg.image?.src) {
    stage.style.backgroundImage = `url("${String(bg.image.src).replace(/"/g, "")}")`;
    stage.style.backgroundSize = "cover";
  }
  for (const el of slide.elements || []) {
    if (el.type === "shape") stage.append(shape(el));
    else if (el.type === "text") {
      const t = textNode(el.content, el.defaultColor);
      if (t) stage.append(h("div", { class: "pp-el", style: { ...box(el), color: el.defaultColor || null } }, t));
    } else if (el.type === "image" && el.src) {
      stage.append(h("div", { class: `pp-el pp-img${String(el.id || "").startsWith("src-") ? " pp-img--source" : ""}`, style: box(el) },
        h("img", { src: el.src, alt: "", loading: "lazy" })));
    } else if (el.type === "line") stage.append(line(el));
    // audio / video / chart / table elements: shown elsewhere (voice panel) or not rendered in preview
  }
  if (highlight) stage.classList.add("is-highlight");

  // Scale the fixed-size stage to the available width.
  const frame = h("div", { class: `pp-frame${thumb ? " pp-frame--thumb" : ""}`, style: { aspectRatio: `${width} / ${height}` },
    "aria-hidden": thumb ? "true" : null }, stage);
  const fit = () => {
    const w = frame.clientWidth;
    if (w) stage.style.transform = `scale(${w / width})`;
  };
  new ResizeObserver(fit).observe(frame);
  return frame;
}
