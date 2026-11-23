// multipart/form-data so'rov tanasini qo'lda yig'adi. Brauzer FormData'ni o'zi kodlasa,
// yuboriladigan baytlarni oldindan bilib bo'lmaydi, imzo esa aynan shu baytlarga qo'yiladi.

const encoder = new TextEncoder();

function boundary() {
  const random = [...crypto.getRandomValues(new Uint8Array(12))].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `----lunch${random}`;
}

// Fayl nomidagi qo'shtirnoq va qator ko'chirish sarlavhani buzmasin.
function safeFilename(name) {
  return name.replace(/["\r\n\\]/g, "_");
}

export function buildMultipart(fieldName, filename, contentType, fileBytes, separator = boundary()) {
  const head = encoder.encode(
    `--${separator}\r\n` +
      `Content-Disposition: form-data; name="${fieldName}"; filename="${safeFilename(filename)}"\r\n` +
      `Content-Type: ${contentType}\r\n\r\n`,
  );
  const tail = encoder.encode(`\r\n--${separator}--\r\n`);
  const body = new Uint8Array(head.length + fileBytes.length + tail.length);
  body.set(head, 0);
  body.set(fileBytes, head.length);
  body.set(tail, head.length + fileBytes.length);
  return { body, contentType: `multipart/form-data; boundary=${separator}` };
}
