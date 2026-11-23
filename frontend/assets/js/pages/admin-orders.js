import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { adminOrderCard } from "../admin-order-card.js";
import { icon } from "../icons.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { initTelegram } from "../telegram.js";
import { emptyState, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-orders", ADMIN_LINKS);

const list = document.getElementById("orders");
const more = document.getElementById("more");
const filters = document.getElementById("filters");
const totalBox = document.getElementById("total-count");
const PAGE_SIZE = 20;

let page = 0;

function query(pageNumber) {
  const params = new URLSearchParams({ page: String(pageNumber), size: String(PAGE_SIZE) });
  for (const name of ["status", "payment_method", "date_from", "date_to"]) {
    if (filters[name].value) params.set(name, filters[name].value);
  }
  if (filters.failed.checked) params.set("notify_status", "failed");
  return `/admin/orders?${params}`;
}

async function load(reset) {
  if (reset) {
    page = 0;
    list.replaceChildren(skeletonRows(3));
  }
  more.disabled = true;
  try {
    const result = await api("GET", query(page + 1));
    page = result.page;
    if (reset) list.replaceChildren();
    totalBox.textContent = `${result.total} ta buyurtma`;
    if (!result.total) {
      list.replaceChildren(emptyState(icon("receipt"), "Buyurtma topilmadi", "Filtrni o'zgartirib ko'ring"));
    } else {
      list.append(...result.items.map(adminOrderCard));
    }
    more.hidden = page * result.size >= result.total;
  } catch (error) {
    if (reset) list.replaceChildren();
    toast(errorText(error), "error");
  } finally {
    more.disabled = false;
  }
}

filters.addEventListener("change", () => load(true));
filters.addEventListener("submit", (event) => {
  event.preventDefault();
  load(true);
});
filters.addEventListener("reset", () => setTimeout(() => load(true)));
more.addEventListener("click", () => load(false));

await load(true);
