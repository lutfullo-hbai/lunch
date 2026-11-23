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

export function dateTime(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
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
