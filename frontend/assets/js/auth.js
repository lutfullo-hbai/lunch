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
};

// Pydantic xabarlari inglizcha keladi: maydonga qarab o'zbekcha matn ko'rsatamiz.
const FIELD_ERRORS = {
  full_name: "Ism kamida 2 harfdan iborat bo'lsin",
  email: "Email manzili noto'g'ri",
  password: "Parolni kiriting",
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
  return MESSAGES[error.code] ?? error.message ?? "Xatolik yuz berdi";
}
