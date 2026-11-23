import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { adminOrderCard } from "../admin-order-card.js";
import { icon } from "../icons.js";
import { ADMIN_LINKS, initials, renderNav } from "../layout.js";
import { backButton, haptic, initTelegram } from "../telegram.js";
import { confirmButton, dateTime, el, emptyState, idFromUrl, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-users", ADMIN_LINKS);
backButton(() => location.assign("/admin/users.html"));

const userId = idFromUrl();
if (userId === null) {
  location.replace("/admin/users.html");
  await new Promise(() => {}); // sahifa almashguncha qolgan kod ishlamasin
}
const profileBox = document.getElementById("profile");
const ordersBox = document.getElementById("orders");
const more = document.getElementById("more");
const PAGE_SIZE = 10;

let page = 0;

function statusButton(user) {
  if (user.role === "admin") return el("p", { className: "hint", text: "Adminni bloklab bo'lmaydi." });
  const change = async (isActive) => {
    try {
      const updated = await api("PATCH", `/admin/users/${user.id}/status`, { is_active: isActive });
      haptic("success");
      toast(isActive ? "User blokdan chiqarildi" : "User bloklandi, barcha sessiyalari yopildi", "success");
      renderProfile(updated);
    } catch (error) {
      haptic("error");
      toast(errorText(error), "error");
    }
  };
  return user.is_active
    ? confirmButton({ label: "Bloklash", confirmLabel: "Rostdan bloklansinmi? Yana bosing", onConfirm: () => change(false) })
    : el("button", { className: "btn", text: "Blokdan chiqarish", attrs: { type: "button" }, on: { click: () => change(true) } });
}

function renderProfile(user) {
  const facts = [
    ["Email", user.email],
    ["Telefon", user.phone ?? "—"],
    ["Rol", user.role === "admin" ? "Admin" : "User"],
    ["Holat", user.is_active ? "Faol" : "Bloklangan"],
    ["Ro'yxatdan o'tgan", dateTime(user.created_at)],
    ["Oxirgi kirish", user.last_login_at ? dateTime(user.last_login_at) : "Hali kirmagan"],
    ["Buyurtmalar", `${user.orders_count} ta`],
  ];
  profileBox.replaceChildren(
    el("div", { className: "profile-head" }, [
      el("span", { className: "avatar", text: initials(user.full_name) || "?" }),
      el("div", {}, [el("div", { className: "order-id", text: user.full_name }), el("div", { className: "hint", text: user.email })]),
    ]),
    el("dl", { className: "facts" }, facts.flatMap(([term, value]) => [el("dt", { text: term }), el("dd", { text: value })])),
    el("div", { className: "form-actions" }, [statusButton(user)]),
  );
}

async function loadOrders(reset) {
  if (reset) {
    page = 0;
    ordersBox.replaceChildren(skeletonRows(2));
  }
  more.disabled = true;
  try {
    const result = await api("GET", `/admin/users/${userId}/orders?page=${page + 1}&size=${PAGE_SIZE}`);
    page = result.page;
    if (reset) ordersBox.replaceChildren();
    if (!result.total) ordersBox.replaceChildren(emptyState(icon("receipt"), "Buyurtma yo'q", "Bu user hali buyurtma bermagan"));
    else ordersBox.append(...result.items.map(adminOrderCard));
    more.hidden = page * result.size >= result.total;
  } catch (error) {
    toast(errorText(error), "error");
  } finally {
    more.disabled = false;
  }
}

more.addEventListener("click", () => loadOrders(false));

try {
  renderProfile(await api("GET", `/admin/users/${userId}`));
  await loadOrders(true);
} catch (error) {
  profileBox.replaceChildren(emptyState(icon("users"), "User topilmadi", errorText(error), { label: "Userlar ro'yxati", href: "/admin/users.html" }));
}
