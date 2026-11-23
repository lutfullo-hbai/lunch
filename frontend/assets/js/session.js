// Tokenlarni saqlash.
// - refresh token qurilmada qoladi (ilova yopilib ochilganda qayta login kerak emas):
//   Telegram SecureStorage (iOS Keychain, Android Keystore) bo'lsa o'sha, aks holda localStorage.
// - access token, imzo kaliti va user faqat sessionStorage'da: ilova yopilganda o'chadi,
//   keyingi ochilishda refresh token bilan yangisi olinadi.

import { secureStorage } from "./telegram.js";

const REFRESH_KEY = "lunch_refresh";
const SESSION_KEY = "lunch_session";

function secureCall(method, ...args) {
  return new Promise((resolve, reject) => {
    try {
      secureStorage[method](...args, (error, value) => (error ? reject(error) : resolve(value)));
    } catch (error) {
      reject(error);
    }
  });
}

async function storeRefresh(token) {
  if (secureStorage) {
    try {
      await secureCall("setItem", REFRESH_KEY, token);
      localStorage.removeItem(REFRESH_KEY);
      return;
    } catch {
      // Qurilma qo'llab-quvvatlamasa, oddiy saqlashga o'tamiz.
    }
  }
  localStorage.setItem(REFRESH_KEY, token);
}

export async function getRefreshToken() {
  if (secureStorage) {
    try {
      const value = await secureCall("getItem", REFRESH_KEY);
      if (value) return value;
    } catch {
      // pastdagi localStorage'ga qaytamiz
    }
  }
  return localStorage.getItem(REFRESH_KEY);
}

export async function saveTokens(tokens) {
  await storeRefresh(tokens.refresh_token);
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({
      access_token: tokens.access_token,
      signing_key: tokens.signing_key,
      user: tokens.user,
    }),
  );
}

export function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

export async function clearTokens() {
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(REFRESH_KEY);
  if (secureStorage) {
    try {
      await secureCall("removeItem", REFRESH_KEY);
    } catch {
      // saqlanmagan bo'lsa ham mayli
    }
  }
}
