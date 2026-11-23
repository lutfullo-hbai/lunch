import { publicPost } from "../api.js";
import { errorText, homeFor, redirectIfLoggedIn } from "../auth.js";
import { saveTokens } from "../session.js";
import { haptic, initTelegram } from "../telegram.js";
import { passwordToggle, setBusy } from "../ui.js";

initTelegram();

const form = document.getElementById("login-form");
const error = document.getElementById("form-error");
const submit = form.querySelector("button[type=submit]");
passwordToggle(form.password);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  setBusy(submit, true);
  try {
    const tokens = await publicPost("/auth/login", {
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
