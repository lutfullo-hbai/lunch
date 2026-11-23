import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { backButton, haptic, initTelegram } from "../telegram.js";
import { confirmButton, el, setBusy, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-menu", ADMIN_LINKS);

const LIST_PAGE = "/admin/menu.html";
const itemId = new URLSearchParams(location.search).get("id");
const form = document.getElementById("item-form");
const title = document.getElementById("title");
const submit = form.querySelector("button[type=submit]");
const formError = document.getElementById("form-error");

let dirty = false;
backButton(() => leave(LIST_PAGE));

function leave(url, message) {
  dirty = false;
  location.assign(message ? `${url}?saved=${encodeURIComponent(message)}` : url);
}

// Saqlanmagan o'zgarish bilan sahifadan chiqishda brauzer ogohlantiradi.
form.addEventListener("input", () => (dirty = true));
window.addEventListener("beforeunload", (event) => {
  if (dirty) event.preventDefault();
});

function clearErrors() {
  formError.textContent = "";
  for (const box of form.querySelectorAll(".field-error")) box.textContent = "";
}

function showError(error) {
  haptic("error");
  const field = error.code === "VALIDATION_ERROR" ? error.details?.[0]?.field?.split(".").pop() : null;
  const box = field && document.getElementById(`error-${field}`);
  if (box) {
    box.textContent = errorText(error);
    form.elements[field]?.focus();
  } else {
    formError.textContent = errorText(error);
  }
}

// "45 000" yoki "45000,50" ham qabul qilinadi.
function parsePrice(text) {
  return text.replace(/\s/g, "").replace(",", ".");
}

function payload() {
  return {
    name: form.name.value.trim(),
    price: parsePrice(form.price.value),
    portion: form.portion.value.trim() || null,
    description: form.description.value.trim() || null,
    category_id: Number(form.category_id.value) || null,
    is_available: form.is_available.checked,
  };
}

async function loadCategories(selectedId) {
  const categories = await api("GET", "/admin/categories");
  form.category_id.append(
    ...categories.map((c) =>
      el("option", { text: c.is_active ? c.name : `${c.name} (yashirin)`, attrs: { value: String(c.id) } }),
    ),
  );
  if (selectedId) form.category_id.value = String(selectedId);
  if (!categories.length) formError.textContent = "Avval kategoriya qo'shing (Kategoriyalar bo'limi)";
}

function fill(item) {
  form.name.value = item.name;
  form.price.value = String(Number(item.price));
  form.portion.value = item.portion ?? "";
  form.description.value = item.description ?? "";
  form.is_available.checked = item.is_available;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  const data = payload();
  if (!data.category_id) {
    document.getElementById("error-category_id").textContent = "Kategoriyani tanlang";
    return;
  }
  setBusy(submit, true);
  try {
    const saved = itemId
      ? await api("PATCH", `/admin/menu/${itemId}`, data)
      : await api("POST", "/admin/menu", data);
    haptic("success");
    leave(LIST_PAGE, `"${saved.name}" saqlandi`);
  } catch (error) {
    showError(error);
    setBusy(submit, false);
  }
});

try {
  if (itemId) {
    title.textContent = "Ovqatni tahrirlash";
    const item = await api("GET", `/admin/menu/${itemId}`);
    fill(item);
    await loadCategories(item.category_id);
    document.getElementById("danger-zone").append(
      confirmButton({
        label: "Ovqatni o'chirish",
        confirmLabel: "Rostdan o'chirilsinmi? Yana bosing",
        onConfirm: async () => {
          try {
            await api("DELETE", `/admin/menu/${itemId}`);
            leave(LIST_PAGE, `"${item.name}" o'chirildi`);
          } catch (error) {
            showError(error);
          }
        },
      }),
    );
  } else {
    await loadCategories(null);
  }
  form.hidden = false;
} catch (error) {
  toast(errorText(error), "error");
  if (error.code === "MENU_ITEM_NOT_FOUND") setTimeout(() => leave(LIST_PAGE), 1500);
}
