import { api } from "../api.js";
import { errorText, requireAdmin } from "../auth.js";
import { icon } from "../icons.js";
import { ADMIN_LINKS, renderNav } from "../layout.js";
import { haptic, initTelegram } from "../telegram.js";
import { confirmButton, el, emptyState, setBusy, skeletonRows, toast } from "../ui.js";

initTelegram();
await requireAdmin();
renderNav("admin-categories", ADMIN_LINKS);

const listBox = document.getElementById("categories");
const addForm = document.getElementById("add-form");
const SORT_STEP = 10; // tartib raqamlari orasida joy qoladi

let categories = [];

async function load() {
  categories = await api("GET", "/admin/categories");
  render();
}

function fail(error) {
  haptic("error");
  toast(errorText(error), "error");
}

// Tartibni o'zgartirish: ro'yxat qaytadan 10, 20, 30… bilan raqamlanadi va faqat
// o'zgargan kategoriyalar saqlanadi (bir xil raqamlilar ham to'g'ri tartiblanadi).
async function move(index, delta) {
  const order = [...categories];
  const [moved] = order.splice(index, 1);
  order.splice(index + delta, 0, moved);
  try {
    for (const [i, category] of order.entries()) {
      const sortOrder = (i + 1) * SORT_STEP;
      if (category.sort_order !== sortOrder) {
        await api("PATCH", `/admin/categories/${category.id}`, { sort_order: sortOrder });
      }
    }
    haptic("light");
  } catch (error) {
    fail(error);
  }
  await load();
}

function editRow(category, row) {
  const input = el("input", { attrs: { type: "text", value: category.name, maxlength: "100", "aria-label": "Kategoriya nomi" } });
  const save = el("button", { className: "btn", text: "Saqlash", attrs: { type: "submit" } });
  const form = el("form", { className: "admin-edit" }, [
    input,
    save,
    el("button", { className: "btn btn-ghost", text: "Bekor", attrs: { type: "button" }, on: { click: render } }),
  ]);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setBusy(save, true);
    try {
      await api("PATCH", `/admin/categories/${category.id}`, { name: input.value });
      toast("Saqlandi", "success");
      await load();
    } catch (error) {
      fail(error);
      setBusy(save, false);
    }
  });
  row.append(form);
  input.focus();
  input.select();
}

function categoryRow(category, index) {
  const row = el("div", { className: `admin-row${category.is_active ? "" : " is-hidden"}` });
  const iconButton = (name, label, onClick) =>
    el("button", { className: "icon-btn", attrs: { type: "button", "aria-label": label, title: label }, on: { click: onClick } }, [icon(name)]);
  const up = iconButton("up", "Yuqoriga", () => move(index, -1));
  const down = iconButton("down", "Pastga", () => move(index, 1));
  up.disabled = index === 0;
  down.disabled = index === categories.length - 1;

  row.append(
    el("div", {}, [
      el("div", { className: "admin-title", text: category.name }),
      el("div", { className: "hint", text: `${category.items_count} ta ovqat${category.is_active ? "" : " · yashirin"}` }),
    ]),
    el("div", { className: "admin-actions" }, [
      up,
      down,
      iconButton("edit", "Nomini o'zgartirish", () => {
        const open = row.querySelector(".admin-edit");
        if (open) open.remove();
        else editRow(category, row);
      }),
      iconButton(category.is_active ? "eye" : "eyeOff", category.is_active ? "Yashirish" : "Ko'rsatish", async () => {
        try {
          await api("PATCH", `/admin/categories/${category.id}`, { is_active: !category.is_active });
          toast(category.is_active ? "Kategoriya menyudan yashirildi" : "Kategoriya menyuda ko'rinadi", "success");
          await load();
        } catch (error) {
          fail(error);
        }
      }),
      confirmButton({
        label: "O'chirish",
        confirmLabel: "Rostdanmi?",
        onConfirm: async () => {
          try {
            await api("DELETE", `/admin/categories/${category.id}`);
            toast(`"${category.name}" o'chirildi`, "success");
            await load();
          } catch (error) {
            fail(error);
          }
        },
      }),
    ]),
  );
  return row;
}

function render() {
  if (!categories.length) {
    listBox.classList.remove("list");
    listBox.replaceChildren(emptyState(icon("list"), "Kategoriya yo'q", "Birinchi kategoriyani yuqorida qo'shing"));
    return;
  }
  listBox.classList.add("list");
  listBox.replaceChildren(...categories.map(categoryRow));
}

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = addForm.querySelector("button");
  const name = addForm.name.value.trim();
  if (!name) return;
  setBusy(button, true);
  try {
    const sortOrder = (categories.length + 1) * SORT_STEP;
    await api("POST", "/admin/categories", { name, sort_order: sortOrder });
    addForm.reset();
    haptic("success");
    toast(`"${name}" qo'shildi`, "success");
    await load();
  } catch (error) {
    fail(error);
  } finally {
    setBusy(button, false);
  }
});

listBox.replaceChildren(skeletonRows(4));
try {
  await load();
} catch (error) {
  listBox.replaceChildren(emptyState(icon("list"), "Yuklab bo'lmadi", errorText(error)));
}
