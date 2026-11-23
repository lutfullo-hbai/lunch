import { api } from "../api.js";
import { errorText, requireUser } from "../auth.js";
import { renderNav } from "../layout.js";
import { backButton, haptic, initTelegram } from "../telegram.js";
import { icon } from "../icons.js";
import { dateTime, el, emptyState, money, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireUser();
renderNav("orders");
backButton(() => location.assign("/"));

const list = document.getElementById("orders");
const more = document.getElementById("more");
const PAGE_SIZE = 20;

const STATUS = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  ready: "Tayyor",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilingan",
};
const PAYMENT = { cash: "Naqd", card: "Karta" };
// Buyurtma yo'li: progress chizig'i shu tartibda to'ladi.
const STEPS = ["new", "accepted", "ready", "delivered"];
const STEP_LABELS = ["Yangi", "Qabul", "Tayyor", "Yetkazildi"];

function progress(status) {
  const reached = STEPS.indexOf(status);
  return [
    el("div", { className: "progress", attrs: { "aria-hidden": "true" } },
      STEPS.map((_, i) => el("span", { className: i <= reached ? "done" : "" })),
    ),
    el("div", { className: "progress-labels", attrs: { "aria-hidden": "true" } }, STEP_LABELS.map((t) => el("span", { text: t }))),
  ];
}

// Bekor qilish ikki bosishda: brauzer oynasi (confirm) Telegram ichida noqulay.
function cancelButton(order, card) {
  let armed = false;
  let timer = null;
  const button = el("button", { className: "btn btn-danger-soft", text: "Bekor qilish", attrs: { type: "button" } });
  button.addEventListener("click", async () => {
    if (!armed) {
      armed = true;
      button.textContent = "Rostdan bekor qilinsinmi? Yana bosing";
      haptic("warning");
      timer = setTimeout(() => {
        armed = false;
        button.textContent = "Bekor qilish";
      }, 4000);
      return;
    }
    clearTimeout(timer);
    button.disabled = true;
    try {
      const updated = await api("POST", `/orders/me/${order.id}/cancel`);
      haptic("success");
      toast(`Buyurtma #${order.id} bekor qilindi`, "success");
      card.replaceWith(orderCard(updated));
    } catch (error) {
      haptic("error");
      toast(error.code === "ORDER_NOT_CANCELLABLE" ? "Buyurtma qabul qilingan, endi bekor qilib bo'lmaydi" : errorText(error), "error");
      const fresh = await api("GET", `/orders/me/${order.id}`).catch(() => null);
      if (fresh) card.replaceWith(orderCard(fresh));
      else button.disabled = false;
    }
  });
  return button;
}

function orderCard(order) {
  const card = el("article", { className: "card" });
  card.append(
    el("div", { className: "order-head" }, [
      el("span", { className: "order-id", text: `#${order.id}` }),
      el("span", { className: `status status-${order.status}`, text: STATUS[order.status] ?? order.status }),
    ]),
    el("div", { className: "hint", text: `${dateTime(order.created_at)} · ${PAYMENT[order.payment_method]}` }),
    ...(order.status === "cancelled" ? [] : progress(order.status)),
    el("div", { className: "order-lines" },
      order.items.map((item) =>
        el("div", { className: "order-line" }, [
          el("span", { text: `${item.name} × ${item.quantity}` }),
          el("span", { text: money(item.subtotal) }),
        ]),
      ),
    ),
    el("div", { className: "summary-row" }, [el("span", { text: "Jami" }), el("span", { className: "total", text: money(order.total_price) })]),
  );
  if (order.can_cancel) card.append(el("div", { className: "order-actions" }, [cancelButton(order, card)]));
  return card;
}

let page = 0;

async function loadMore() {
  more.disabled = true;
  try {
    const result = await api("GET", `/orders/me?page=${page + 1}&size=${PAGE_SIZE}`);
    page = result.page;
    if (page === 1) list.replaceChildren();
    list.append(...result.items.map(orderCard));
    if (!result.total) {
      list.replaceChildren(
        emptyState(icon("receipt"), "Hali buyurtma yo'q", "Birinchi buyurtmangizni menyudan bering", { label: "Menyuga o'tish", href: "/" }),
      );
    }
    more.hidden = page * result.size >= result.total;
  } catch (error) {
    toast(errorText(error), "error");
  } finally {
    more.disabled = false;
  }
}

more.addEventListener("click", loadMore);

const created = new URLSearchParams(location.search).get("created");
if (created) {
  toast(`Buyurtma #${created} qabul qilindi`, "success");
  history.replaceState(null, "", location.pathname);
}
list.replaceChildren(skeletonRows(3));
await loadMore();
