// Imzo backend bilan bir xil chiqishi kerak. Qiymatlar backend/tests/test_signature_vectors.py
// dagi bilan aynan bir xil: biror tomonda algoritm o'zgarsa, ikkalasidan biri yiqiladi.
import assert from "node:assert/strict";
import { test } from "node:test";

import { buildStringToSign, computeSignature, sha256Hex } from "../assets/js/signing.js";

const encoder = new TextEncoder();

test("POST with body, query and a non-ASCII key", async () => {
  const body = encoder.encode('{"items":[{"menu_item_id":1,"quantity":2}],"payment_method":"card"}');
  const bodyHash = await sha256Hex(body);
  assert.equal(bodyHash, "df572ebce81b9b2e4c2f5a218c97612023120d051e94bf0f7107801384d14f56");
  const toSign = buildStringToSign("POST", "/api/v1/orders?x=1", "1795400000", "abc123nonce", bodyHash);
  assert.equal(
    await computeSignature("test-signing-key-ж", toSign),
    "00e7eb262bc6c10c587d7c5cf231af567cf6b614677fd83311115222e8244d94",
  );
});

test("GET without body", async () => {
  const toSign = buildStringToSign("get", "/api/v1/me", "1", "n", await sha256Hex(new Uint8Array()));
  assert.equal(
    await computeSignature("k", toSign),
    "702e92d12ca5dd8b3aa10d691718f1c8b860a3d366d02ac06cac34aed6d455d9",
  );
});
