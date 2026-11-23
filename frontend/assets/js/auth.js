// Kirish holati: sahifani himoyalash, roliga qarab yo'naltirish, chiqish, xato matnlari.

import { api, refreshSession } from "./api.js";
import { clearTokens, getSession } from "./session.js";

export const LOGIN_PAGE = "/login.html";

export function homeFor(user) {
  return user.role === "admin" ? "/admin.html" : "/";
}

async function currentSession() {
  try {
    return getSession() ?? (await refreshSession());
  } catch {
    return null;
  }
}

// Kirmagan userni login sahifasiga yuboradi. Kirgan bo'lsa, user'ni qaytaradi.
export async function requireUser() {
  const session = await currentSession();
  if (!session) {
    location.replace(LOGIN_PAGE);
    return new Promise(() => {}); // sahifa almashguncha kutadi
  }
  return session.user;
}

// Faqat admin uchun sahifalar: oddiy user menyuga qaytariladi.
export async function requireAdmin() {
  const user = await requireUser();
  if (user.role !== "admin") {
    location.replace("/");
    return new Promise(() => {});
  }
  return user;
}

export async function redirectIfLoggedIn() {
  const session = await currentSession();
  if (session) location.replace(homeFor(session.user));
}

export async function logout() {
  try {
    await api("POST", "/auth/logout");
  } catch {
    // Server javob bermasa ham qurilmadagi tokenlar o'chiriladi.
  }
  await clearTokens();
  location.replace(LOGIN_PAGE);
}

const MESSAGES = {
  INVALID_CREDENTIALS: "Email yoki parol noto'g'ri",
  EMAIL_TAKEN: "Bu email bilan ro'yxatdan o'tilgan. Kirish sahifasiga o'ting",
  USER_INACTIVE: "Hisobingiz bloklangan. Administratorga murojaat qiling",
  NETWORK_ERROR: "Internet aloqasini tekshiring",
  FORBIDDEN: "Bu amal faqat admin uchun",
  CATEGORY_EXISTS: "Bu nomli kategoriya bor",
  CATEGORY_NOT_FOUND: "Kategoriya topilmadi (o'chirilgan bo'lishi mumkin)",
  MENU_ITEM_NOT_FOUND: "Ovqat topilmadi (o'chirilgan bo'lishi mumkin)",
  INVALID_IMAGE: "Faqat JPEG, PNG yoki WebP rasm yuklang",
  IMAGE_TOO_LARGE: "Rasm juda katta",
  REQUEST_TOO_LARGE: "Fayl juda katta",
  ORDER_NOT_FOUND: "Buyurtma topilmadi",
  INVALID_STATUS_TRANSITION: "Bu holatga o'tkazib bo'lmaydi",
  ORDER_ALREADY_NOTIFIED: "Buyurtma guruhga allaqachon yuborilgan",
  TELEGRAM_NOT_CONFIGURED: "Telegram bot sozlanmagan (BOT_TOKEN, ORDERS_GROUP_CHAT_ID)",
  USER_NOT_FOUND: "User topilmadi",
  CANNOT_BLOCK_ADMIN: "Adminni bloklab bo'lmaydi",
};

// Pydantic xabarlari inglizcha keladi: maydonga qarab o'zbekcha matn ko'rsatamiz.
const FIELD_ERRORS = {
  full_name: "Ism kamida 2 harfdan iborat bo'lsin",
  email: "Email manzili noto'g'ri",
  password: "Parolni kiriting",
  name: "Nomni kiriting",
  price: "Narx musbat son bo'lsin (masalan 45000)",
  category_id: "Kategoriyani tanlang",
  portion: "Porsiya 50 belgidan oshmasin",
  sort_order: "Tartib raqami noto'g'ri",
  date_from: "Boshlanish sanasi tugash sanasidan keyin bo'lmasin",
};
const OWN_MESSAGE_PREFIX = "Value error, ";

export function errorText(error) {
  if (error.code === "TOO_MANY_REQUESTS") {
    const minutes = Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60));
    return `Urinishlar juda ko'p. ${minutes} daqiqadan keyin qayta urinib ko'ring`;
  }
  if (error.code === "VALIDATION_ERROR" && Array.isArray(error.details) && error.details.length) {
    const { field, message } = error.details[0];
    // Backend'da o'zimiz yozgan tekshiruvlar (parol uzunligi va h.k.) allaqachon o'zbekcha.
    if (message.startsWith(OWN_MESSAGE_PREFIX)) return message.slice(OWN_MESSAGE_PREFIX.length);
    return FIELD_ERRORS[field.split(".").pop()] ?? "Ma'lumotlar noto'g'ri";
  }
  if (error.code === "CATEGORY_NOT_EMPTY") {
    const count = error.details?.items_count ?? "";
    return `Kategoriyada ${count} ta ovqat bor. Avval ularni o'chiring yoki boshqa kategoriyaga o'tkazing`;
  }
  return MESSAGES[error.code] ?? error.message ?? "Xatolik yuz berdi";
}
