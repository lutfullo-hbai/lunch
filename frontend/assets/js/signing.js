// So'rov imzosi (HMAC-SHA256). Backend'dagi app/core/signature.py bilan bir xil:
//   METHOD \n PATH[?QUERY] \n X-Timestamp \n X-Nonce \n sha256(body)
// Brauzerda ham, Node'da ham ishlaydi (Web Crypto).

const encoder = new TextEncoder();

function toHex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(bytes) {
  return toHex(await crypto.subtle.digest("SHA-256", bytes));
}

export function buildStringToSign(method, path, timestamp, nonce, bodyHash) {
  return [method.toUpperCase(), path, timestamp, nonce, bodyHash].join("\n");
}

export async function computeSignature(signingKey, stringToSign) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(signingKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toHex(await crypto.subtle.sign("HMAC", key, encoder.encode(stringToSign)));
}

function newNonce() {
  return toHex(crypto.getRandomValues(new Uint8Array(16)));
}

// `path` so'rov yuboriladigan ko'rinishda bo'lishi kerak: prefix va query bilan.
export async function signatureHeaders(signingKey, method, path, bodyBytes) {
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = newNonce();
  const stringToSign = buildStringToSign(method, path, timestamp, nonce, await sha256Hex(bodyBytes));
  return {
    "X-Timestamp": timestamp,
    "X-Nonce": nonce,
    "X-Signature": await computeSignature(signingKey, stringToSign),
  };
}
