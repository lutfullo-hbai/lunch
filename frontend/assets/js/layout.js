// Sahifalarning yuqori menyusi.

import { logout } from "./auth.js";
import { cartCount } from "./cart.js";
import { el } from "./ui.js";

const LINKS = [
  { href: "/", label: "Menyu", page: "menu" },
  { href: "/cart.html", label: "Savat", page: "cart" },
  { href: "/orders.html", label: "Buyurtmalarim", page: "orders" },
];

export function renderNav(active) {
  const links = LINKS.map(({ href, label, page }) => {
    const link = el("a", { text: label, attrs: { href } });
    if (page === active) link.setAttribute("aria-current", "page");
    if (page === "cart") {
      const badge = el("span", { className: "badge", attrs: { id: "cart-badge" } });
      link.append(badge);
    }
    return link;
  });
  const exit = el("a", { text: "Chiqish", attrs: { href: "#" }, on: { click: (e) => (e.preventDefault(), logout()) } });
  document.body.prepend(el("nav", { className: "nav" }, [...links, exit]));
  updateCartBadge();
}

export function updateCartBadge() {
  const badge = document.getElementById("cart-badge");
  if (!badge) return;
  const count = cartCount();
  badge.textContent = String(count);
  badge.hidden = count === 0;
}
