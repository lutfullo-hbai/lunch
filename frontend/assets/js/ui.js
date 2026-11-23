// Kichik DOM yordamchilari. User matni faqat textContent orqali qo'yiladi (XSS bo'lmasin).

import { CURRENCY } from "./config.js";

export function el(tag, { className, text, attrs, on } = {}, children = []) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  for (const [name, value] of Object.entries(attrs ?? {})) node.setAttribute(name, value);
  for (const [event, handler] of Object.entries(on ?? {})) node.addEventListener(event, handler);
  node.append(...children);
  return node;
}

export function money(amount) {
  const value = Number(amount);
  const digits = Number.isInteger(value) ? 0 : 2;
  const text = value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${text.replaceAll(",", " ")} ${CURRENCY}`;
}

// "Bugun 12:30", "Kecha 18:05" yoki "21.11.2026 09:10".
export function dateTime(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const today = new Date();
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return `Bugun ${time}`;
  if (d.toDateString() === yesterday.toDateString()) return `Kecha ${time}`;
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${time}`;
}

// Ovqat rasmi; rasm bo'lmasa nomining bosh harfi.
export function dishPhoto(item) {
  const box = el("div", { className: "dish-photo" });
  if (item.thumb_url) box.append(el("img", { attrs: { src: item.thumb_url, alt: "", loading: "lazy" } }));
  else box.textContent = item.name.trim()[0]?.toUpperCase() ?? "";
  return box;
}

// Bo'sh holat: ikonka, sarlavha, izoh va ixtiyoriy tugma (havola).
export function emptyState(iconNode, title, text, action) {
  const box = el("div", { className: "empty" }, [
    el("div", { className: "empty-icon" }, [iconNode]),
    el("strong", { text: title }),
    el("span", { text }),
  ]);
  if (action) box.append(el("a", { className: "btn", text: action.label, attrs: { href: action.href } }));
  return box;
}

// Ma'lumot yuklanguncha ko'rinadigan kulrang qatorlar.
export function skeletonRows(count) {
  return el(
    "div",
    { className: "list", attrs: { "aria-busy": "true", "aria-label": "Yuklanmoqda" } },
    Array.from({ length: count }, () =>
      el("div", { className: "dish" }, [
        el("div", { className: "dish-photo skeleton" }),
        el("div", {}, [
          el("div", { className: "skeleton skeleton-line skeleton-wide" }),
          el("div", { className: "skeleton skeleton-line skeleton-narrow" }),
        ]),
        el("div", {}),
      ]),
    ),
  );
}

let toastTimer = null;

export function toast(message, kind = "info") {
  let box = document.getElementById("toast");
  if (!box) {
    box = el("div", { attrs: { id: "toast", role: "status", "aria-live": "polite" } });
    document.body.append(box);
  }
  box.textContent = message;
  box.className = `toast toast-${kind} toast-visible`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("toast-visible"), 3500);
}

export function setBusy(button, isBusy) {
  button.disabled = isBusy;
  button.classList.toggle("is-busy", isBusy);
}

// Parol maydoniga "Ko'rsatish / Yashirish" tugmasi.
export function passwordToggle(input) {
  const button = el("button", { text: "Ko'rsatish", attrs: { type: "button", "aria-pressed": "false" } });
  button.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? "Yashirish" : "Ko'rsatish";
    button.setAttribute("aria-pressed", String(show));
    input.focus();
  });
  const wrap = el("div", { className: "password" });
  input.replaceWith(wrap);
  wrap.append(input, button);
}

// Xavfli amal (o'chirish) ikki bosishda: brauzer oynasi (confirm) Telegram ichida noqulay.
export function confirmButton({ label, confirmLabel, className = "btn btn-danger-soft", onConfirm }) {
  const button = el("button", { className, text: label, attrs: { type: "button" } });
  let armed = false;
  let timer = null;
  const reset = () => {
    armed = false;
    button.textContent = label;
  };
  button.addEventListener("click", async () => {
    if (!armed) {
      armed = true;
      button.textContent = confirmLabel;
      timer = setTimeout(reset, 4000);
      return;
    }
    clearTimeout(timer);
    button.disabled = true;
    try {
      await onConfirm();
    } finally {
      button.disabled = false;
      reset();
    }
  });
  return button;
}

// Keyingi sahifada bir marta ko'rsatiladigan xabar. URL orqali uzatilmaydi: begona
// havola ilova nomidan istalgan matnni chiqara olmasin.
const FLASH_KEY = "lunch_flash";

export function flash(message) {
  try {
    sessionStorage.setItem(FLASH_KEY, message);
  } catch {
    // saqlab bo'lmasa, xabarsiz davom etamiz
  }
}

export function showFlash() {
  try {
    const message = sessionStorage.getItem(FLASH_KEY);
    sessionStorage.removeItem(FLASH_KEY);
    if (message) toast(message, "success");
  } catch {
    // sessionStorage yo'q bo'lsa ham sahifa ishlaydi
  }
}

// URL'dagi `?id=` faqat musbat butun son bo'lsa qabul qilinadi.
export function idFromUrl(name = "id") {
  const value = new URLSearchParams(location.search).get(name);
  return value && /^[1-9]\d{0,9}$/.test(value) ? value : null;
}
