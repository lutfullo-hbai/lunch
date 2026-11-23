// Yuqori panel: ilova nomi, profil (ism, email, chiqish) va ikonkali bo'limlar.

import { logout } from "./auth.js";
import { cartCount } from "./cart.js";
import { icon } from "./icons.js";
import { getSession } from "./session.js";
import { el } from "./ui.js";

const LINKS = [
  { href: "/", label: "Menyu", page: "menu", icon: "menu" },
  { href: "/cart.html", label: "Savat", page: "cart", icon: "bag" },
  { href: "/orders.html", label: "Buyurtmalar", page: "orders", icon: "receipt" },
];

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function profile(user) {
  const pop = el("div", { className: "profile-pop", attrs: { role: "dialog", "aria-label": "Profil" } }, [
    el("strong", { text: user.full_name }),
    el("span", { className: "hint", text: user.email }),
    el("button", { className: "btn btn-ghost", text: "Chiqish", attrs: { type: "button" }, on: { click: logout } }),
  ]);
  pop.hidden = true;
  const button = el("button", {
    className: "avatar",
    text: initials(user.full_name) || "?",
    attrs: { type: "button", "aria-label": "Profil", "aria-expanded": "false" },
  });
  const toggle = (open) => {
    pop.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
  };
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    toggle(pop.hidden);
  });
  document.addEventListener("click", (event) => {
    if (!pop.contains(event.target)) toggle(false);
  });
  return el("div", { className: "profile" }, [button, pop]);
}

export function renderNav(active) {
  const user = getSession()?.user;
  const tabs = LINKS.map(({ href, label, page, icon: name }) => {
    const iconWrap = el("span", { className: "icon-wrap" }, [icon(name)]);
    if (page === "cart") iconWrap.append(el("span", { className: "badge", attrs: { id: "cart-badge" } }));
    const link = el("a", { attrs: { href } }, [iconWrap, el("span", { text: label })]);
    if (page === active) link.setAttribute("aria-current", "page");
    return link;
  });
  const header = el("header", { className: "topbar" }, [
    el("div", { className: "topbar-inner" }, [
      el("div", { className: "brand" }, [el("span", { className: "brand-mark", text: "🍽" }), el("span", { text: "Lunch" })]),
      user ? profile(user) : "",
    ]),
    el("nav", { className: "tabbar", attrs: { "aria-label": "Bo'limlar" } }, tabs),
  ]);
  document.body.prepend(header);
  // Kategoriyalar paneli yuqori panel ostida yopishib tursin.
  document.documentElement.style.setProperty("--topbar-height", `${header.offsetHeight}px`);
  updateCartBadge();
}

export function updateCartBadge() {
  const badge = document.getElementById("cart-badge");
  if (!badge) return;
  const count = cartCount();
  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count === 0;
}
