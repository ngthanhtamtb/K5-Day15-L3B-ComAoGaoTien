/* Slide narration player: one track per slide with clickable segment markers (A1..An),
 * each marker coloured by its source label. Uses a native <audio> element. */
import { h, icon } from "../core/dom.js";
import { mmss } from "../core/format.js";
import { LABELS } from "./ui.js";

export function audioTrack(audio, { onSegment } = {}) {
  if (!audio?.url) {
    return h("p", { class: "small muted row" }, icon("mic", 16), "Slide này chưa có giọng đọc.");
  }
  const player = h("audio", { src: audio.url, preload: "metadata" });
  const time = h("span", { class: "track__time mono" }, `0:00 / ${mmss(audio.duration)}`);
  const head = h("div", { class: "track__head" });
  const playBtn = h("button", { class: "btn btn--sm", type: "button", "aria-label": "Phát giọng đọc slide" }, icon("play", 16));
  const bar = h("div", { class: "track__bar" });
  const total = audio.duration || 1;

  const markers = (audio.markers || []).map((m) => {
    const tone = LABELS[m.nhan]?.tone || "muted";
    const seg = h("button", {
      class: `track__seg track__seg--${tone}`, type: "button",
      style: { left: `${(m.start / total) * 100}%`, width: `${Math.max(1.5, ((m.end - m.start) / total) * 100)}%` },
      title: `${m.segment} · ${mmss(m.start)}–${mmss(m.end)} · ${LABELS[m.nhan]?.text || m.nhan}`,
      onClick: () => { player.currentTime = m.start; player.play(); onSegment?.(m.segment); },
    }, m.segment);
    bar.append(seg);
    return { m, seg };
  });
  bar.append(head);

  playBtn.addEventListener("click", () => (player.paused ? player.play() : player.pause()));
  player.addEventListener("play", () => { playBtn.replaceChildren(icon("pause", 16)); playBtn.setAttribute("aria-label", "Tạm dừng"); });
  player.addEventListener("pause", () => { playBtn.replaceChildren(icon("play", 16)); playBtn.setAttribute("aria-label", "Phát giọng đọc slide"); });
  player.addEventListener("timeupdate", () => {
    const t = player.currentTime;
    time.textContent = `${mmss(t)} / ${mmss(audio.duration)}`;
    head.style.left = `${(t / total) * 100}%`;
    for (const { m, seg } of markers) seg.classList.toggle("is-playing", t >= m.start && t < m.end);
  });

  return h("div", { class: "track" }, playBtn, h("div", { class: "track__main" }, bar, time), player);
}
