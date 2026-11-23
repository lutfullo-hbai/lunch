import { publicPost } from "../api.js";
import { PASSWORD_MIN_LENGTH } from "../config.js";
import { errorText, homeFor, redirectIfLoggedIn } from "../auth.js";
import { saveTokens } from "../session.js";
import { haptic, initTelegram, telegramName } from "../telegram.js";
import { passwordToggle, setBusy } from "../ui.js";

initTelegram();

const form = document.getElementById("register-form");
const error = document.getElementById("form-error");
const submit = form.querySelector("button[type=submit]");
passwordToggle(form.password);
document.getElementById("password-hint").textContent = `Kamida ${PASSWORD_MIN_LENGTH} belgi`;
const nameFromTelegram = telegramName();
if (nameFromTelegram && !form.full_name.value) form.full_name.value = nameFromTelegram;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  setBusy(submit, true);
  try {
    const tokens = await publicPost("/auth/register", {
      full_name: form.full_name.value.trim(),
      email: form.email.value.trim(),
      password: form.password.value,
    });
    await saveTokens(tokens);
    haptic("success");
    location.replace(homeFor(tokens.user));
  } catch (e) {
    haptic("error");
    error.textContent = errorText(e);
    setBusy(submit, false);
  }
});

// Forma tayyor bo'lgach tekshiramiz: kirgan user bu sahifada qolmasin.
await redirectIfLoggedIn();
