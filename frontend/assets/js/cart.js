// Savat: qurilmada (localStorage), har bir user uchun alohida.
// Narx bu yerda faqat ko'rsatish uchun; buyurtma summasini server bazadagi narxdan hisoblaydi.

import { getSession } from "./session.js";

function storageKey() {
  return `lunch_cart_${getSession()?.user?.id ?? "guest"}`;
}

export function getCart() {
  try {
    return JSON.parse(localStorage.getItem(storageKey())) ?? {};
  } catch {
    return {};
  }
}

function save(cart) {
  localStorage.setItem(storageKey(), JSON.stringify(cart));
}

export function quantityOf(itemId) {
  return getCart()[itemId]?.quantity ?? 0;
}

// Miqdor 0 dan pastga tushmaydi; 0 bo'lsa ovqat savatdan olib tashlanadi.
export function setQuantity(item, quantity) {
  const cart = getCart();
  const next = Math.max(0, Math.floor(quantity));
  if (next === 0) {
    delete cart[item.id];
  } else {
    cart[item.id] = {
      id: item.id,
      name: item.name,
      price: item.price,
      portion: item.portion ?? null,
      thumb_url: item.thumb_url ?? null,
      quantity: next,
    };
  }
  save(cart);
  return next;
}

export function cartLines() {
  return Object.values(getCart());
}

export function cartCount() {
  return cartLines().reduce((sum, line) => sum + line.quantity, 0);
}

export function cartTotal() {
  return cartLines().reduce((sum, line) => sum + Number(line.price) * line.quantity, 0);
}

export function removeItems(itemIds) {
  const cart = getCart();
  for (const id of itemIds) delete cart[id];
  save(cart);
}

export function clearCart() {
  localStorage.removeItem(storageKey());
}
