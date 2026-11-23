// Kutubxonasiz ustunli grafik (SVG), bitta qator uchun.
// Ustun eni <= 24px, tepasi 4px yumaloq, pasti to'g'ri; hover/fokusda tooltip;
// har bir qiymat jadval ko'rinishida ham bor (tooltip yagona yo'l bo'lmasin).

import { el } from "./ui.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const HEIGHT = 180;
const PAD = { top: 12, right: 8, bottom: 24, left: 44 };
const MAX_BAR = 24;
const RADIUS = 4;
const TICKS = 3;

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  return node;
}

// O'qdagi chegaralar "chiroyli" sonlar bo'lsin: 0, 50 000, 100 000, 150 000.
// Qadam (max / TICKS) yaxlitlanadi, shunda eng baland ustun o'qning tepasiga yaqin turadi.
export function niceMax(value) {
  if (value <= 0) return TICKS;
  const rawStep = value / TICKS;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 1.5, 2, 2.5, 3, 5, 10].find((m) => m * magnitude >= rawStep) * magnitude;
  return step * TICKS;
}

// Tepasi yumaloq, pasti to'g'ri ustun.
function barPath(x, y, width, height) {
  const r = Math.min(RADIUS, width / 2, height);
  const bottom = y + height;
  return `M${x},${bottom}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${bottom}Z`;
}

/**
 * @param points  [{ label, shortLabel, value }]
 * @param options { formatAxis, describe(point) -> [[name, value], …], caption }
 */
export function barChart(points, { formatAxis, describe, caption }) {
  const width = Math.max(320, points.length * 28 + PAD.left + PAD.right);
  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const max = niceMax(Math.max(...points.map((p) => p.value)));
  const band = plotW / points.length;
  const barW = Math.min(MAX_BAR, band - 2); // 2px oraliq: qo'shni ustunlar tegmasin

  const chart = svg("svg", { viewBox: `0 0 ${width} ${HEIGHT}`, class: "bar-chart", role: "img", "aria-label": caption });
  for (let i = 0; i <= TICKS; i++) {
    const value = (max / TICKS) * i;
    const y = PAD.top + plotH - (value / max) * plotH;
    chart.append(svg("line", { x1: PAD.left, x2: width - PAD.right, y1: y, y2: y, class: "grid" }));
    const tick = svg("text", { x: PAD.left - 6, y: y + 4, class: "axis", "text-anchor": "end" });
    tick.textContent = formatAxis(value);
    chart.append(tick);
  }

  const tooltip = el("div", { className: "chart-tooltip", attrs: { role: "status" } });
  tooltip.hidden = true;
  const wrap = el("div", { className: "chart-wrap" }, [chart, tooltip]);

  const show = (point, bar, centerX) => {
    for (const other of chart.querySelectorAll(".bar")) other.classList.toggle("dim", other !== bar);
    tooltip.replaceChildren(
      el("strong", { text: point.label }),
      ...describe(point).map(([name, value]) => el("div", {}, [el("span", { className: "hint", text: `${name} ` }), el("b", { text: value })])),
    );
    tooltip.hidden = false;
    const leftPct = (centerX / width) * 100;
    tooltip.style.left = `${Math.min(Math.max(leftPct, 15), 85)}%`;
  };
  const hide = () => {
    tooltip.hidden = true;
    for (const bar of chart.querySelectorAll(".bar")) bar.classList.remove("dim");
  };

  // X o'qida faqat birinchi, o'rta va oxirgi kun: har birini yozsak, o'qib bo'lmaydi.
  const labelled = new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]);
  points.forEach((point, i) => {
    const centerX = PAD.left + band * i + band / 2;
    const h = (point.value / max) * plotH;
    const bar = svg("path", { d: barPath(centerX - barW / 2, PAD.top + plotH - h, barW, Math.max(h, 0)), class: "bar" });
    // Bosiladigan joy ustundan katta: butun ustun kengligi va balandligi.
    const hit = svg("rect", {
      x: PAD.left + band * i, y: PAD.top, width: band, height: plotH,
      class: "hit", tabindex: 0, "aria-label": `${point.label}: ${describe(point).map((d) => d.join(" ")).join(", ")}`,
    });
    hit.addEventListener("pointerenter", () => show(point, bar, centerX));
    hit.addEventListener("focus", () => show(point, bar, centerX));
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("blur", hide);
    chart.append(bar, hit);
    if (labelled.has(i)) {
      const anchor = i === 0 ? "start" : i === points.length - 1 ? "end" : "middle";
      const text = svg("text", { x: i === 0 ? PAD.left + band * i : i === points.length - 1 ? PAD.left + band * (i + 1) : centerX, y: HEIGHT - 6, class: "axis", "text-anchor": anchor });
      text.textContent = point.shortLabel;
      chart.append(text);
    }
  });
  return wrap;
}
