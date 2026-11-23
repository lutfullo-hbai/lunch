// Rasmni yuklashdan oldin brauzerda kichraytirish: telefondagi 5-10 MB rasm
// bir necha yuz KB bo'lib ketadi. Server baribir o'zi ham WebP'ga o'giradi.

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIDE = 1600;
const QUALITY = 0.85;

function canvasToBlob(canvas, type) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, QUALITY));
}

// Kichraytirilgan rasm (Blob) qaytaradi. Brauzer qila olmasa, asl fayl qaytadi.
export async function shrinkImage(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file;
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  // WebP'ni qo'llamaydigan brauzer (eski Safari) PNG qaytaradi: unda JPEG'ga o'tamiz.
  const webp = await canvasToBlob(canvas, "image/webp");
  const blob = webp?.type === "image/webp" ? webp : await canvasToBlob(canvas, "image/jpeg");
  return blob && blob.size < file.size ? blob : file;
}
