// Admin uchun buyurtma kartasi: buyurtmalar sahifasi va user sahifasida bir xil.

import { api } from "./api.js";
import { errorText } from "./auth.js";
import { PAYMENT_LABELS, STATUS_LABELS } from "./labels.js";
import { haptic } from "./telegram.js";
import { confirmButton, dateTime, el, money, toast } from "./ui.js";

// Keyingi holatga o'tkazuvchi tugma matni.
const ACTION_LABELS = {
  accepted: "Qabul qilish",
  ready: "Tayyor",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilish",
};

const NOTIFY_LABELS = {
  failed: "Guruhga yetib bormagan",
  pending: "Guruhga yuborilmoqda",
};

export function adminOrderCard(order) {
  const card = el("article", { className: "card" });
  const replace = (updated) => card.replaceWith(adminOrderCard(updated));

  async function refresh() {
    try {
      replace(await api("GET", `/admin/orders/${order.id}`));
    } catch {
      // kartani o'zgarishsiz qoldiramiz
    }
  }

  async function setStatus(status) {
    try {
      replace(await api("PATCH", `/admin/orders/${order.id}/status`, { status }));
      haptic("success");
      toast(`#${order.id}: ${STATUS_LABELS[status]}`, "success");
    } catch (error) {
      haptic("error");
      toast(
        error.code === "INVALID_STATUS_TRANSITION"
          ? `#${order.id} holati allaqachon o'zgargan, yangilandi`
          : errorText(error),
        "error",
      );
      await refresh();
    }
  }

  async function resend() {
    try {
      replace(await api("POST", `/admin/orders/${order.id}/notify`));
      toast(`#${order.id} guruhga qayta yuborilmoqda`, "success");
    } catch (error) {
      toast(errorText(error), "error");
      await refresh();
    }
  }

  const actions = order.allowed_statuses.map((status) =>
    status === "cancelled"
      ? confirmButton({ label: ACTION_LABELS[status], confirmLabel: "Rostdanmi?", onConfirm: () => setStatus(status) })
      : el("button", { className: "btn", text: ACTION_LABELS[status], attrs: { type: "button" }, on: { click: () => setStatus(status) } }),
  );
  if (order.notify_status !== "sent") {
    actions.push(el("button", { className: "btn btn-ghost", text: "Guruhga qayta yuborish", attrs: { type: "button" }, on: { click: resend } }));
  }

  const badges = [el("span", { className: `status status-${order.status}`, text: STATUS_LABELS[order.status] })];
  if (NOTIFY_LABELS[order.notify_status]) {
    badges.push(el("span", { className: `pill notify-${order.notify_status}`, text: NOTIFY_LABELS[order.notify_status] }));
  }

  card.append(
    el("div", { className: "order-head" }, [el("span", { className: "order-id", text: `#${order.id}` }), el("div", { className: "badges" }, badges)]),
    el("div", { className: "order-user" }, [
      el("a", { text: order.user.full_name, attrs: { href: `/admin/user.html?id=${order.user.id}` } }),
      el("span", { className: "hint", text: ` · ${order.user.email}` }),
    ]),
    el("div", { className: "hint", text: `${dateTime(order.created_at)} · ${PAYMENT_LABELS[order.payment_method]}` }),
    el(
      "div",
      { className: "order-lines" },
      order.items.map((item) =>
        el("div", { className: "order-line" }, [el("span", { text: `${item.name} × ${item.quantity}` }), el("span", { text: money(item.subtotal) })]),
      ),
    ),
    el("div", { className: "summary-row" }, [el("span", { text: "Jami" }), el("span", { className: "total", text: money(order.total_price) })]),
  );
  if (actions.length) card.append(el("div", { className: "order-admin-actions" }, actions));
  return card;
}
