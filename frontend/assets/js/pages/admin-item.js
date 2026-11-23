import { api, apiRaw } from "../api.js";
import { IMAGE_MAX_UPLOAD_MB } from "../config.js";
import { ACCEPTED_TYPES, shrinkImage } from "../image.js";
import { buildMultipart } from "../multipart.js";
import { errorText, requireAdmin } from "../auth.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { backButton, haptic, initTelegram } from "../telegram.js";
import { confirmButton, el, setBusy, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-menu", ADMIN_LINKS);

const LIST_PAGE = "/admin/menu.html";
let itemId = new URLSearchParams(location.search).get("id");
const form = document.getElementById("item-form");
const title = document.getElementById("title");
const submit = form.querySelector("button[type=submit]");
const formError = document.getElementById("form-error");
const imageInput = document.getElementById("image-input");
const preview = document.getElementById("preview");
const noImage = document.getElementById("no-image");
const imageError = document.getElementById("error-image");
const removeSlot = document.getElementById("remove-image");

let pendingImage = null; // tanlangan, hali yuklanmagan rasm (Blob)
let previewUrl = null;

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

function showImage(url) {
  preview.hidden = !url;
  noImage.hidden = Boolean(url);
  if (url) preview.src = url;
}

function renderRemoveButton(item) {
  removeSlot.replaceChildren();
  if (!item?.image_url) return;
  removeSlot.append(
    confirmButton({
      label: "Rasmni o'chirish",
      confirmLabel: "Rostdanmi?",
      onConfirm: async () => {
        try {
          const updated = await api("DELETE", `/admin/menu/${item.id}/image`);
          showImage(null);
          renderRemoveButton(updated);
          toast("Rasm o'chirildi", "success");
        } catch (error) {
          imageError.textContent = errorText(error);
        }
      },
    }),
  );
}

imageInput.addEventListener("change", async () => {
  imageError.textContent = "";
  const file = imageInput.files[0];
  imageInput.value = ""; // o'sha faylni qayta tanlash ham ishlasin
  if (!file) return;
  if (!ACCEPTED_TYPES.includes(file.type)) {
    imageError.textContent = "Faqat JPEG, PNG yoki WebP rasm tanlang";
    return;
  }
  const image = await shrinkImage(file);
  if (image.size > IMAGE_MAX_UPLOAD_MB * 1024 * 1024) {
    imageError.textContent = `Rasm ${IMAGE_MAX_UPLOAD_MB} MB dan katta`;
    return;
  }
  pendingImage = image;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(image);
  showImage(previewUrl);
  dirty = true;
});

async function uploadImage(id) {
  const extension = { "image/webp": "webp", "image/png": "png" }[pendingImage.type] ?? "jpg";
  const bytes = new Uint8Array(await pendingImage.arrayBuffer());
  const { body, contentType } = buildMultipart("image", `rasm.${extension}`, pendingImage.type, bytes);
  await apiRaw("PUT", `/admin/menu/${id}/image`, body, contentType);
  pendingImage = null;
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
  let saved;
  try {
    saved = itemId ? await api("PATCH", `/admin/menu/${itemId}`, data) : await api("POST", "/admin/menu", data);
  } catch (error) {
    showError(error);
    setBusy(submit, false);
    return;
  }
  // Ovqat saqlandi; endi shu sahifa uning tahrirlash sahifasi (rasm yuklanmasa ham yo'qolmaydi).
  itemId = String(saved.id);
  history.replaceState(null, "", `?id=${itemId}`);
  title.textContent = "Ovqatni tahrirlash";
  if (pendingImage) {
    try {
      await uploadImage(itemId);
    } catch (error) {
      haptic("error");
      imageError.textContent = `Ovqat saqlandi, lekin rasm yuklanmadi: ${errorText(error)}`;
      setBusy(submit, false);
      return;
    }
  }
  haptic("success");
  leave(LIST_PAGE, `"${saved.name}" saqlandi`);
});

try {
  if (itemId) {
    title.textContent = "Ovqatni tahrirlash";
    const item = await api("GET", `/admin/menu/${itemId}`);
    fill(item);
    showImage(item.image_url);
    renderRemoveButton(item);
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
