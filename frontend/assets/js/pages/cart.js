import { api } from "../api.js";
import { errorText, requireUser } from "../auth.js";
import { cartLines, cartTotal, clearCart, removeItems, setQuantity } from "../cart.js";
import { renderNav, updateCartBadge } from "../layout.js";
import { backButton, haptic, initTelegram, mainButton } from "../telegram.js";
import { el, money, toast } from "../ui.js";

initTelegram();
await requireUser();
renderNav("cart");
backButton(() => location.assign("/"));

const linesBox = document.getElementById("lines");
const summary = document.getElementById("summary");
const totalBox = document.getElementById("total");
const paymentForm = document.getElementById("payment");
const submit = mainButton(document.getElementById("place-order"));

const PAYMENT_TEXT = { cash: "naqd", card: "karta" };

function payment() {
  return paymentForm.payment_method.value || null;
}

function lineRow(line) {
  const change = (delta) => {
    setQuantity(line, line.quantity + delta);
    haptic("light");
    render();
  };
  return el("div", { className: "line" }, [
    el("div", { className: "row" }, [
      el("div", {}, [
        el("div", { className: "item-name", text: line.name }),
        el("div", { className: "hint", text: `${money(line.price)} × ${line.quantity}` }),
      ]),
      el("strong", { text: money(Number(line.price) * line.quantity) }),
    ]),
    el("div", { className: "stepper" }, [
      el("button", { text: "−", attrs: { type: "button", "aria-label": `${line.name}: kamaytirish` }, on: { click: () => change(-1) } }),
      el("output", { text: String(line.quantity) }),
      el("button", { text: "+", attrs: { type: "button", "aria-label": `${line.name}: ko'paytirish` }, on: { click: () => change(1) } }),
    ]),
  ]);
}

function render() {
  updateCartBadge();
  const lines = cartLines();
  if (!lines.length) {
    linesBox.replaceChildren(
      el("p", { className: "empty" }, ["Savat bo'sh. ", el("a", { text: "Menyuga o'tish", attrs: { href: "/" } })]),
    );
    summary.hidden = true;
    submit.hide();
    return;
  }
  linesBox.replaceChildren(...lines.map(lineRow));
  totalBox.textContent = money(cartTotal());
  summary.hidden = false;
  const method = payment();
  submit.show(method ? `Buyurtma berish (${PAYMENT_TEXT[method]})` : "To'lov turini tanlang", placeOrder);
  submit.enabled(Boolean(method));
}

// Savatdagi narx va nomlarni menyudagi hozirgi holat bilan tenglashtiradi.
async function syncWithMenu() {
  const menu = await api("GET", "/menu");
  const current = new Map(menu.map((item) => [item.id, item]));
  const gone = cartLines().filter((line) => !current.has(line.id));
  if (gone.length) {
    removeItems(gone.map((line) => line.id));
    toast(`Sotuvda yo'q: ${gone.map((l) => l.name).join(", ")}. Savatdan olib tashlandi`, "error");
  }
  for (const line of cartLines()) setQuantity(current.get(line.id), line.quantity);
}

let sending = false;

async function placeOrder() {
  const method = payment();
  if (sending || !method || !cartLines().length) return;
  sending = true;
  submit.busy(true);
  try {
    const order = await api("POST", "/orders", {
      items: cartLines().map((line) => ({ menu_item_id: line.id, quantity: line.quantity })),
      payment_method: method,
    });
    clearCart();
    haptic("success");
    location.replace(`/orders.html?created=${order.id}`);
  } catch (error) {
    haptic("error");
    if (error.code === "ITEMS_UNAVAILABLE") {
      const ids = new Set(error.details?.menu_item_ids ?? []);
      const names = cartLines().filter((l) => ids.has(l.id)).map((l) => l.name);
      removeItems([...ids]);
      toast(`Sotuvda yo'q: ${names.join(", ")}. Savatdan olib tashlandi, qayta tekshiring`, "error");
    } else {
      toast(errorText(error), "error");
    }
    submit.busy(false);
    render();
  } finally {
    sending = false;
  }
}

paymentForm.addEventListener("change", () => {
  haptic("light");
  render();
});

render();
try {
  await syncWithMenu();
} catch {
  // Menyu yuklanmasa ham savat ko'rinadi; server buyurtmada baribir tekshiradi.
}
render();
