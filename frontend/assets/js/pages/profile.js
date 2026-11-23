import { api } from "../api.js";
import { errorText, requireUser } from "../auth.js";
import { ADMIN_LINKS, renderNav, USER_LINKS } from "../layout.js";
import { backButton, haptic, initTelegram } from "../telegram.js";
import { passwordToggle, setBusy, toast } from "../ui.js";

// Register va backend bilan bir xil qoida (server baribir o'zi tekshiradi).
const PASSWORD_MIN_LENGTH = 8;

initTelegram();
const user = await requireUser();
renderNav("profile", user.role === "admin" ? ADMIN_LINKS : USER_LINKS);
backButton(() => history.back());

document.getElementById("full-name").textContent = user.full_name;
document.getElementById("email").textContent = user.email;
document.getElementById("role").textContent = user.role === "admin" ? "Admin" : "Mijoz";

const form = document.getElementById("password-form");
const submit = form.querySelector("button[type=submit]");
for (const input of [form.current_password, form.new_password, form.confirm_password]) passwordToggle(input);

function clearErrors() {
  for (const box of form.querySelectorAll(".field-error")) box.textContent = "";
}

function fieldError(field, message) {
  document.getElementById(`error-${field}`).textContent = message;
  form.elements[field].focus();
  haptic("error");
}

// Serverga yubormasdan oldin aniq bo'lgan xatolarni shu yerda aytamiz.
function validate() {
  const { current_password: current, new_password: next, confirm_password: confirm } = form;
  if (!current.value) return fieldError("current_password", "Joriy parolni kiriting"), false;
  if (next.value.length < PASSWORD_MIN_LENGTH) {
    return fieldError("new_password", `Yangi parol kamida ${PASSWORD_MIN_LENGTH} belgi bo'lsin`), false;
  }
  if (next.value === current.value) return fieldError("new_password", "Yangi parol joriy paroldan farq qilsin"), false;
  if (confirm.value !== next.value) return fieldError("confirm_password", "Parollar mos kelmadi"), false;
  return true;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  if (!validate()) return;
  setBusy(submit, true);
  try {
    await api("POST", "/auth/change-password", {
      current_password: form.current_password.value,
      new_password: form.new_password.value,
    });
    form.reset();
    haptic("success");
    toast("Parol almashtirildi. Boshqa qurilmalardan chiqarildingiz", "success");
  } catch (error) {
    const field = error.code === "VALIDATION_ERROR" ? error.details?.[0]?.field?.split(".").pop() : null;
    if (field && document.getElementById(`error-${field}`)) fieldError(field, errorText(error));
    else toast(errorText(error), "error");
  } finally {
    setBusy(submit, false);
  }
});
