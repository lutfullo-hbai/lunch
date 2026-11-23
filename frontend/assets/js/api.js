// API bilan ishlashning yagona joyi: token, imzo va token eskirganda yangilash.

import { API_PREFIX } from "./config.js";
import { clearTokens, getRefreshToken, getSession, saveTokens } from "./session.js";
import { signatureHeaders } from "./signing.js";

const encoder = new TextEncoder();

// Shu kodlar kelsa, token yangilanib so'rov bir marta qaytariladi.
const REFRESHABLE = new Set(["INVALID_TOKEN", "SESSION_REVOKED", "NOT_AUTHENTICATED"]);

export class ApiError extends Error {
  constructor(status, code, message, details, headers) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = Number(headers?.get("Retry-After")) || null;
  }
}

async function parse(response) {
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (response.ok) return body;
  const error = body?.error ?? {};
  throw new ApiError(
    response.status,
    error.code ?? "NETWORK_ERROR",
    error.message ?? "Server bilan bog'lanib bo'lmadi",
    error.details,
    response.headers,
  );
}

// `body`: JSON uchun obyekt, yoki tayyor baytlar uchun RawBody (apiRaw orqali).
function encodeBody(body) {
  if (body === undefined) return { bytes: new Uint8Array(), contentType: null };
  if (body instanceof RawBody) return { bytes: body.bytes, contentType: body.contentType };
  return { bytes: encoder.encode(JSON.stringify(body)), contentType: "application/json" };
}

class RawBody {
  constructor(bytes, contentType) {
    this.bytes = bytes;
    this.contentType = contentType;
  }
}

async function send(method, path, body, session) {
  const url = API_PREFIX + path;
  const { bytes, contentType } = encodeBody(body);
  const headers = {};
  if (contentType) headers["Content-Type"] = contentType;
  if (session) {
    headers.Authorization = `Bearer ${session.access_token}`;
    Object.assign(headers, await signatureHeaders(session.signing_key, method, url, bytes));
  }
  let response;
  try {
    response = await fetch(url, { method, headers, body: contentType ? bytes : undefined });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Internet aloqasini tekshiring");
  }
  return parse(response);
}

// Login, register va refresh: imzosiz.
export function publicPost(path, body) {
  return send("POST", path, body, null);
}

// Bitta sahifada bir vaqtda faqat bitta refresh ketadi ("single-flight").
let refreshing = null;

export function refreshSession() {
  refreshing ??= (async () => {
    const refreshToken = await getRefreshToken();
    if (!refreshToken) return null;
    try {
      const tokens = await publicPost("/auth/refresh", { refresh_token: refreshToken });
      await saveTokens(tokens);
      return getSession();
    } catch (error) {
      if (error.status === 401 || error.status === 403) await clearTokens();
      throw error;
    }
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function api(method, path, body) {
  let session = getSession() ?? (await refreshSession());
  if (!session) throw new ApiError(401, "NOT_AUTHENTICATED", "Tizimga kiring");
  try {
    return await send(method, path, body, session);
  } catch (error) {
    if (error.status !== 401 || !REFRESHABLE.has(error.code)) throw error;
    session = await refreshSession();
    if (!session) throw error;
    return send(method, path, body, session);
  }
}

// Tayyor baytlarni (masalan multipart) imzolab yuborish.
export function apiRaw(method, path, bytes, contentType) {
  return api(method, path, new RawBody(bytes, contentType));
}
