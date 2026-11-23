import { api } from "../api.js";
import { requireUser } from "../auth.js";
import { cartCount, cartTotal, quantityOf, setQuantity } from "../cart.js";
import { renderNav, updateCartBadge } from "../layout.js";
import { haptic, initTelegram, mainButton } from "../telegram.js";
import { el, money, toast } from "../ui.js";

initTelegram();
await requireUser();
renderNav("menu");

const tabsBox = document.getElementById("tabs");
const itemsBox = document.getElementById("items");
const toCart = mainButton(document.getElementById("to-cart"));

let categories = [];
let items = [];
let activeCategory = null; // null = hammasi

function stepper(item, refresh) {
  const quantity = quantityOf(item.id);
  const change = (delta) => {
    setQuantity(item, quantity + delta);
    haptic("light");
    refresh();
  };
  if (quantity === 0) {
    return el("button", {
      className: "btn add-button",
      text: "Qo'shish",
      attrs: { type: "button" },
      on: { click: () => change(1) },
    });
  }
  return el("div", { className: "stepper" }, [
    el("button", { text: "−", attrs: { type: "button", "aria-label": "Kamaytirish" }, on: { click: () => change(-1) } }),
    el("output", { text: String(quantity) }),
    el("button", { text: "+", attrs: { type: "button", "aria-label": "Ko'paytirish" }, on: { click: () => change(1) } }),
  ]);
}

function itemCard(item) {
  const card = el("article", { className: "item" });
  const controls = el("div");
  const refresh = () => {
    controls.replaceChildren(stepper(item, refresh));
    updateCartBar();
  };
  const photo = item.thumb_url
    ? el("img", { attrs: { src: item.thumb_url, alt: item.name, loading: "lazy" } })
    : el("div", { className: "no-photo", attrs: { "aria-hidden": "true" } });
  const body = el("div", { className: "item-body" }, [
    el("span", { className: "item-name", text: item.name }),
    item.portion ? el("span", { className: "hint", text: item.portion }) : "",
    el("span", { className: "item-price", text: money(item.price) }),
    controls,
  ]);
  card.append(photo, body);
  refresh();
  return card;
}

function renderTabs() {
  const tab = (id, name) =>
    el("button", {
      className: "tab",
      text: name,
      attrs: { type: "button", "aria-pressed": String(activeCategory === id) },
      on: {
        click: () => {
          activeCategory = id;
          renderTabs();
          renderItems();
        },
      },
    });
  tabsBox.replaceChildren(tab(null, "Hammasi"), ...categories.map((c) => tab(c.id, c.name)));
}

function renderItems() {
  const visible = activeCategory === null ? items : items.filter((i) => i.category_id === activeCategory);
  if (!visible.length) {
    itemsBox.replaceChildren(el("p", { className: "empty", text: "Hozircha ovqat yo'q" }));
    return;
  }
  itemsBox.replaceChildren(...visible.map(itemCard));
}

function updateCartBar() {
  updateCartBadge();
  const count = cartCount();
  if (count === 0) toCart.hide();
  else toCart.show(`Savat: ${count} ta — ${money(cartTotal())}`, () => location.assign("/cart.html"));
}

try {
  [categories, items] = await Promise.all([api("GET", "/categories"), api("GET", "/menu")]);
  renderTabs();
  renderItems();
  updateCartBar();
} catch (error) {
  itemsBox.replaceChildren(el("p", { className: "empty", text: "Menyuni yuklab bo'lmadi" }));
  toast(error.message, "error");
}
