import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { barChart } from "../bar-chart.js";
import { CURRENCY } from "../config.js";
import { icon } from "../icons.js";
import { STATUS_LABELS } from "../labels.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { haptic, initTelegram } from "../telegram.js";
import { dateTime, el, emptyState, money, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-dashboard", ADMIN_LINKS);

const periodBox = document.getElementById("period");
const tilesBox = document.getElementById("tiles");
const chartBox = document.getElementById("chart");
const statusBox = document.getElementById("statuses");
const topBox = document.getElementById("top");
const recentBox = document.getElementById("recent");
const RECENT_LIMIT = 10;
const PERIOD_KEY = "lunch_dashboard_period";

const PERIODS = [
  { value: "today", label: "Bugun", caption: "bugun" },
  { value: "7d", label: "7 kun", caption: "so'nggi 7 kun" },
  { value: "30d", label: "30 kun", caption: "so'nggi 30 kun" },
];

function savedPeriod() {
  try {
    return localStorage.getItem(PERIOD_KEY) ?? "today";
  } catch {
    return "today";
  }
}

let period = PERIODS.some((p) => p.value === savedPeriod()) ? savedPeriod() : "today";

// O'q uchun ixcham son: 45 000 -> "45 ming", 1 250 000 -> "1,3 mln".
function compact(value) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString("uz", { maximumFractionDigits: 1 })} mln`;
  if (value >= 1_000) return `${Math.round(value / 1_000)} ming`;
  return String(Math.round(value));
}

function shortDate(iso) {
  const [, month, day] = iso.split("-");
  return `${day}.${month}`;
}

function fullDate(iso) {
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}

function tile(label, value, sub, href) {
  return el(href ? "a" : "div", { className: "tile", attrs: href ? { href } : {} }, [
    el("div", { className: "tile-label", text: label }),
    el("div", { className: "tile-value", text: value }),
    el("div", { className: "tile-sub", text: sub }),
  ]);
}

function renderTiles(stats) {
  tilesBox.replaceChildren(
    tile("Buyurtmalar", String(stats.orders.total), `${stats.orders.by_status.cancelled} ta bekor qilingan`),
    tile("Tushum", money(stats.revenue.total), `naqd ${money(stats.revenue.cash)} · karta ${money(stats.revenue.card)}`),
    tile("Ochiq buyurtmalar", String(stats.pending_orders), "hozir bajarilishi kerak", "/admin/orders.html"),
    tile("Yangi userlar", String(stats.users.new), `jami ${stats.users.total} ta`, "/admin/users.html"),
  );
}

function renderChart(stats) {
  if (stats.daily.length < 2) {
    chartBox.replaceChildren(el("p", { className: "hint", text: "Kunlik grafik 7 va 30 kunlik davrda ko'rinadi." }));
    return;
  }
  const points = stats.daily.map((d) => ({
    label: fullDate(d.date),
    shortLabel: shortDate(d.date),
    value: Number(d.revenue),
    orders: d.orders,
    revenue: d.revenue,
  }));
  const caption = `Kunlik tushum, ${CURRENCY}`;
  const table = el("table", { className: "data-table" }, [
    el("thead", {}, [el("tr", {}, [el("th", { text: "Kun" }), el("th", { text: "Buyurtmalar" }), el("th", { text: "Tushum" })])]),
    el("tbody", {}, points.map((p) => el("tr", {}, [el("td", { text: p.label }), el("td", { text: String(p.orders) }), el("td", { text: money(p.revenue) })]))),
  ]);
  chartBox.replaceChildren(
    barChart(points, {
      caption,
      formatAxis: compact,
      describe: (p) => [["Tushum", money(p.revenue)], ["Buyurtmalar", `${p.orders} ta`]],
    }),
    el("details", {}, [el("summary", { text: "Jadval ko'rinishi" }), table]),
  );
}

function renderStatuses(stats) {
  statusBox.replaceChildren(
    ...Object.entries(stats.orders.by_status).map(([status, count]) =>
      el("div", { className: "summary-row" }, [
        el("span", { className: `status status-${status}`, text: STATUS_LABELS[status] }),
        el("strong", { text: String(count) }),
      ]),
    ),
  );
}

function renderTop(stats) {
  if (!stats.top_items.length) {
    topBox.replaceChildren(el("p", { className: "hint", text: "Bu davrda sotuv bo'lmagan." }));
    return;
  }
  topBox.replaceChildren(
    ...stats.top_items.map((item, i) =>
      el("div", { className: "rank-row" }, [
        el("span", { className: "rank", text: String(i + 1) }),
        el("div", {}, [el("div", { className: "dish-name", text: item.name }), el("div", { className: "hint", text: `${item.quantity} ta sotilgan` })]),
        el("strong", { text: money(item.revenue) }),
      ]),
    ),
  );
}

async function renderRecent() {
  const result = await api("GET", `/admin/orders?page=1&size=${RECENT_LIMIT}`);
  if (!result.items.length) {
    recentBox.replaceChildren(emptyState(icon("receipt"), "Hali buyurtma yo'q", "Yangi buyurtmalar shu yerda ko'rinadi"));
    return;
  }
  recentBox.replaceChildren(
    ...result.items.map((order) =>
      el("a", { className: "recent-row", attrs: { href: "/admin/orders.html" } }, [
        el("strong", { text: `#${order.id}` }),
        el("div", {}, [el("div", { text: order.user.full_name }), el("div", { className: "hint", text: dateTime(order.created_at) })]),
        el("div", { className: "badges" }, [
          el("span", { className: `status status-${order.status}`, text: STATUS_LABELS[order.status] }),
          el("strong", { text: money(order.total_price) }),
        ]),
      ]),
    ),
  );
}

function renderPeriods() {
  periodBox.replaceChildren(
    ...PERIODS.map((p) =>
      el("button", {
        text: p.label,
        attrs: { type: "button", "aria-pressed": String(p.value === period) },
        on: {
          click: () => {
            if (p.value === period) return;
            period = p.value;
            try {
              localStorage.setItem(PERIOD_KEY, period);
            } catch {
              // saqlab bo'lmasa ham ishlayveradi
            }
            haptic("light");
            renderPeriods();
            loadStats();
          },
        },
      }),
    ),
  );
}

async function loadStats() {
  tilesBox.setAttribute("aria-busy", "true");
  try {
    const stats = await api("GET", `/admin/stats?period=${period}`);
    document.getElementById("period-caption").textContent =
      `${PERIODS.find((p) => p.value === period).caption}: ${shortDate(stats.date_from)} – ${shortDate(stats.date_to)}`;
    renderTiles(stats);
    renderChart(stats);
    renderStatuses(stats);
    renderTop(stats);
  } catch (error) {
    toast(errorText(error), "error");
  } finally {
    tilesBox.removeAttribute("aria-busy");
  }
}

renderPeriods();
await Promise.all([loadStats(), renderRecent().catch((error) => toast(errorText(error), "error"))]);
