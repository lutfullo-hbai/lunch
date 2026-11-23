// Telegram Web App bilan ishlash. Brauzerda ochilganda ham sahifa ishlaydi:
// Telegram tugmalari o'rniga oddiy HTML tugmalar ko'rsatiladi.

const tg = window.Telegram?.WebApp;

// Skript brauzerda ham yuklanadi, lekin initData faqat Telegram ichida to'ladi.
export const inTelegram = Boolean(tg && tg.initData);

export function initTelegram() {
  if (!inTelegram) return;
  tg.ready();
  tg.expand();
  document.documentElement.classList.add("in-telegram");
}

export function haptic(kind) {
  if (!inTelegram || !tg.HapticFeedback) return;
  if (kind === "success" || kind === "error" || kind === "warning") {
    tg.HapticFeedback.notificationOccurred(kind);
  } else {
    tg.HapticFeedback.impactOccurred("light");
  }
}

// Pastdagi asosiy tugma. Telegram'dan tashqarida `fallback` HTML tugmasi ishlatiladi.
export function mainButton(fallback) {
  let handler = null;
  return {
    show(text, onClick) {
      handler = onClick;
      if (inTelegram) {
        tg.MainButton.offClick(this._click);
        tg.MainButton.setText(text);
        tg.MainButton.onClick(this._click);
        tg.MainButton.enable();
        tg.MainButton.show();
      } else {
        fallback.textContent = text;
        fallback.hidden = false;
        fallback.disabled = false;
        fallback.onclick = () => handler?.();
      }
    },
    hide() {
      if (inTelegram) tg.MainButton.hide();
      else fallback.hidden = true;
    },
    enabled(isEnabled) {
      if (inTelegram) {
        if (isEnabled) tg.MainButton.enable();
        else tg.MainButton.disable();
      } else {
        fallback.disabled = !isEnabled;
      }
    },
    busy(isBusy) {
      if (inTelegram) {
        if (isBusy) tg.MainButton.showProgress(false);
        else tg.MainButton.hideProgress();
      } else {
        fallback.disabled = isBusy;
      }
    },
    _click: () => handler?.(),
  };
}

// Telegram'ning "orqaga" tugmasi. Brauzerda sahifadagi havolalar yetarli.
export function backButton(onClick) {
  if (!inTelegram) return;
  tg.BackButton.onClick(onClick);
  tg.BackButton.show();
}

// Telegram'dagi ism (register formasini to'ldirish uchun). Faqat ko'rsatish uchun ishlatiladi.
export function telegramName() {
  const user = inTelegram ? tg.initDataUnsafe?.user : null;
  return user ? [user.first_name, user.last_name].filter(Boolean).join(" ") : "";
}

export const secureStorage = inTelegram && tg.isVersionAtLeast?.("9.0") ? tg.SecureStorage : null;
