import { api } from "../api.js";
import { errorText, requireUser } from "../auth.js";
import { cartCount, cartTotal, quantityOf, setQuantity } from "../cart.js";
import { icon } from "../icons.js";
import { renderNav, updateCartBadge } from "../layout.js";
import { haptic, initTelegram, mainButton } from "../telegram.js";
import { dishPhoto, el, emptyState, money, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireUser();
renderNav("menu");

const chipsBox = document.getElementById("chips");
const content = document.getElementById("content");
const toCart = mainButton(document.getElementById("to-cart"));

let categories = [];
let items = [];
let activeCategory = null; // null = hammasi

content.replaceChildren(skeletonRows(5));

function controls(item, rerender) {
  const quantity = quantityOf(item.id);
  const change = (delta) => {
    setQuantity(item, quantity + delta);
    haptic("light");
    rerender();
  };
  if (quantity === 0) {
    return el(
      "button",
      { className: "add", attrs: { type: "button", "aria-label": `${item.name}: savatga qo'shish` }, on: { click: () => change(1) } },
      [icon("plus")],
    );
  }
  return el("div", { className: "stepper" }, [
    el("button", { attrs: { type: "button", "aria-label": `${item.name}: kamaytirish` }, on: { click: () => change(-1) } }, [icon("minus")]),
    el("output", { text: String(quantity), attrs: { "aria-live": "polite" } }),
    el("button", { attrs: { type: "button", "aria-label": `${item.name}: ko'paytirish` }, on: { click: () => change(1) } }, [icon("plus")]),
  ]);
}

function dishRow(item) {
  const action = el("div");
  const rerender = () => {
    action.replaceChildren(controls(item, rerender));
    updateCartBar();
  };
  const row = el("article", { className: "dish" }, [
    dishPhoto(item),
    el("div", {}, [
      el("div", { className: "dish-name", text: item.name }),
      item.portion ? el("div", { className: "hint", text: item.portion }) : "",
      el("div", { className: "dish-price", text: money(item.price) }),
    ]),
    action,
  ]);
  action.replaceChildren(controls(item, rerender));
  return row;
}

function renderChips() {
  const chip = (id, name) =>
    el("button", {
      className: "chip",
      text: name,
      attrs: { type: "button", "aria-pressed": String(activeCategory === id) },
      on: {
        click: () => {
          activeCategory = id;
          haptic("light");
          renderChips();
          renderItems();
          window.scrollTo({ top: 0 });
        },
      },
    });
  chipsBox.replaceChildren(chip(null, "Hammasi"), ...categories.map((c) => chip(c.id, c.name)));
}

function renderItems() {
  if (!items.length) {
    content.replaceChildren(emptyState(icon("menu"), "Menyu hozircha bo'sh", "Ovqatlar qo'shilganda shu yerda ko'rinadi"));
    return;
  }
  const shown = activeCategory === null ? categories : categories.filter((c) => c.id === activeCategory);
  const sections = shown
    .map((category) => {
      const dishes = items.filter((i) => i.category_id === category.id);
      if (!dishes.length) return null;
      return el("section", {}, [el("h2", { text: category.name }), el("div", { className: "list" }, dishes.map(dishRow))]);
    })
    .filter(Boolean);
  content.replaceChildren(...(sections.length ? sections : [emptyState(icon("menu"), "Bu bo'limda ovqat yo'q", "Boshqa bo'limni tanlang")]));
}

function updateCartBar() {
  updateCartBadge();
  const count = cartCount();
  if (count === 0) toCart.hide();
  else toCart.show(`Savat · ${count} ta · ${money(cartTotal())}`, () => location.assign("/cart.html"));
}

try {
  [categories, items] = await Promise.all([api("GET", "/categories"), api("GET", "/menu")]);
  renderChips();
  renderItems();
  updateCartBar();
} catch (error) {
  content.replaceChildren(emptyState(icon("menu"), "Menyuni yuklab bo'lmadi", errorText(error), { label: "Qayta urinish", href: "/" }));
  toast(errorText(error), "error");
}
