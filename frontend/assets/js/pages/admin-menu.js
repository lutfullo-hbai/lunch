import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { icon } from "../icons.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { haptic, initTelegram } from "../telegram.js";
import { dishPhoto, el, emptyState, money, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-menu", ADMIN_LINKS);

const listBox = document.getElementById("items");
const more = document.getElementById("more");
const filters = document.getElementById("filters");
const PAGE_SIZE = 30;
const SEARCH_DELAY_MS = 300;

let page = 0;

function query(pageNumber) {
  const params = new URLSearchParams({ page: String(pageNumber), size: String(PAGE_SIZE) });
  const search = filters.search.value.trim();
  if (search) params.set("search", search);
  if (filters.category.value) params.set("category_id", filters.category.value);
  if (filters.available.value) params.set("is_available", filters.available.value);
  return `/admin/menu?${params}`;
}

function availabilityButton(item) {
  const button = el("button", {
    className: `pill availability ${item.is_available ? "on" : "off"}`,
    text: item.is_available ? "Sotuvda" : "Tugagan",
    attrs: { type: "button", "aria-label": `${item.name}: ${item.is_available ? "sotuvdan olish" : "sotuvga qo'yish"}` },
  });
  button.addEventListener("click", async (event) => {
    event.preventDefault(); // qator havolasi ochilmasin
    button.disabled = true;
    try {
      const updated = await api("PATCH", `/admin/menu/${item.id}`, { is_available: !item.is_available });
      haptic("light");
      button.closest(".admin-dish").replaceWith(itemRow(updated));
    } catch (error) {
      toast(errorText(error), "error");
      button.disabled = false;
    }
  });
  return button;
}

function itemRow(item) {
  return el("a", { className: "admin-dish", attrs: { href: `/admin/item.html?id=${item.id}` } }, [
    dishPhoto(item),
    el("div", {}, [
      el("div", { className: "dish-name", text: item.name }),
      el("div", { className: "hint", text: [item.category_name ?? "Kategoriyasiz", item.portion].filter(Boolean).join(" · ") }),
    ]),
    el("div", { className: "admin-dish-side" }, [el("strong", { text: money(item.price) }), availabilityButton(item)]),
  ]);
}

async function load(reset) {
  if (reset) {
    page = 0;
    listBox.replaceChildren(skeletonRows(5));
  }
  more.disabled = true;
  try {
    const result = await api("GET", query(page + 1));
    page = result.page;
    if (reset) listBox.replaceChildren();
    if (!result.total) {
      listBox.classList.remove("list");
      listBox.replaceChildren(
        emptyState(icon("menu"), "Ovqat topilmadi", "Filtrni o'zgartiring yoki yangi ovqat qo'shing", {
          label: "Ovqat qo'shish",
          href: "/admin/item.html",
        }),
      );
    } else {
      listBox.classList.add("list");
      listBox.append(...result.items.map(itemRow));
    }
    more.hidden = page * result.size >= result.total;
  } catch (error) {
    toast(errorText(error), "error");
  } finally {
    more.disabled = false;
  }
}

async function loadCategories() {
  const categories = await api("GET", "/admin/categories");
  filters.category.append(
    ...categories.map((c) => el("option", { text: c.is_active ? c.name : `${c.name} (yashirin)`, attrs: { value: String(c.id) } })),
  );
}

let searchTimer = null;
filters.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => load(true), SEARCH_DELAY_MS);
});
filters.category.addEventListener("change", () => load(true));
filters.available.addEventListener("change", () => load(true));
filters.addEventListener("submit", (event) => event.preventDefault());
more.addEventListener("click", () => load(false));

const saved = new URLSearchParams(location.search).get("saved");
if (saved) {
  toast(saved, "success");
  history.replaceState(null, "", location.pathname);
}

await Promise.all([loadCategories().catch(() => {}), load(true)]);
