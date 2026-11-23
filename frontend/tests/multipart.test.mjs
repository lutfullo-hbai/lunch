import assert from "node:assert/strict";
import { test } from "node:test";

import { buildMultipart } from "../assets/js/multipart.js";

test("builds a valid single-file multipart body", () => {
  const file = new Uint8Array([0, 1, 2, 255]);
  const { body, contentType } = buildMultipart("image", "rasm.webp", "image/webp", file, "XYZ");
  assert.equal(contentType, "multipart/form-data; boundary=XYZ");
  const text = Buffer.from(body).toString("latin1");
  assert.ok(text.startsWith('--XYZ\r\nContent-Disposition: form-data; name="image"; filename="rasm.webp"\r\nContent-Type: image/webp\r\n\r\n'));
  assert.ok(text.endsWith("\r\n--XYZ--\r\n"));
  // Fayl baytlari o'zgarmasdan ichida turadi (0 va 255 ham).
  assert.ok(Buffer.from(body).includes(Buffer.from(file)));
});

test("filename cannot break the header", () => {
  const { body } = buildMultipart("image", 'a"b\r\nc.png', "image/png", new Uint8Array([1]), "B");
  const text = Buffer.from(body).toString("latin1");
  assert.ok(text.includes('filename="a_b__c.png"'));
});
