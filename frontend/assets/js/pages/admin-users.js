import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { icon } from "../icons.js";
import { ADMIN_LINKS, initials, renderNav } from "../layout.js";
import { initTelegram } from "../telegram.js";
import { dateTime, el, emptyState, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-users", ADMIN_LINKS);

const list = document.getElementById("users");
const more = document.getElementById("more");
const filters = document.getElementById("filters");
const totalBox = document.getElementById("total-count");
const PAGE_SIZE = 30;
const SEARCH_DELAY_MS = 300;

let page = 0;

function query(pageNumber) {
  const params = new URLSearchParams({ page: String(pageNumber), size: String(PAGE_SIZE) });
  const search = filters.search.value.trim();
  if (search) params.set("search", search);
  if (filters.role.value) params.set("role", filters.role.value);
  if (filters.is_active.value) params.set("is_active", filters.is_active.value);
  return `/admin/users?${params}`;
}

function userRow(user) {
  const badges = [];
  if (user.role === "admin") badges.push(el("span", { className: "pill pill-accent", text: "Admin" }));
  if (!user.is_active) badges.push(el("span", { className: "pill pill-danger", text: "Bloklangan" }));
  const lastLogin = user.last_login_at ? `oxirgi kirish: ${dateTime(user.last_login_at)}` : "hali kirmagan";
  return el("a", { className: "user-row", attrs: { href: `/admin/user.html?id=${user.id}` } }, [
    el("span", { className: "avatar", text: initials(user.full_name) || "?" }),
    el("div", {}, [
      el("div", { className: "dish-name", text: user.full_name }),
      el("div", { className: "hint", text: user.email }),
      el("div", { className: "hint", text: `${user.orders_count} ta buyurtma · ${lastLogin}` }),
    ]),
    el("div", { className: "badges" }, badges),
  ]);
}

async function load(reset) {
  if (reset) {
    page = 0;
    list.replaceChildren(skeletonRows(4));
  }
  more.disabled = true;
  try {
    const result = await api("GET", query(page + 1));
    page = result.page;
    if (reset) list.replaceChildren();
    totalBox.textContent = `${result.total} ta user`;
    if (!result.total) {
      list.classList.remove("list");
      list.replaceChildren(emptyState(icon("users"), "User topilmadi", "Qidiruv yoki filtrni o'zgartiring"));
    } else {
      list.classList.add("list");
      list.append(...result.items.map(userRow));
    }
    more.hidden = page * result.size >= result.total;
  } catch (error) {
    if (reset) list.replaceChildren();
    toast(errorText(error), "error");
  } finally {
    more.disabled = false;
  }
}

let searchTimer = null;
filters.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => load(true), SEARCH_DELAY_MS);
});
filters.role.addEventListener("change", () => load(true));
filters.is_active.addEventListener("change", () => load(true));
filters.addEventListener("submit", (event) => event.preventDefault());
more.addEventListener("click", () => load(false));

await load(true);
