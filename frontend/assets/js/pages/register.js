import { publicPost } from "../api.js";
import { errorText, homeFor, redirectIfLoggedIn } from "../auth.js";
import { saveTokens } from "../session.js";
import { haptic, initTelegram } from "../telegram.js";
import { setBusy } from "../ui.js";

initTelegram();
await redirectIfLoggedIn();

const form = document.getElementById("register-form");
const error = document.getElementById("form-error");
const submit = form.querySelector("button[type=submit]");

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
