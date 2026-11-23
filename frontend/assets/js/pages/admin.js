import { logout, requireUser } from "../auth.js";
import { initTelegram } from "../telegram.js";

initTelegram();
const user = await requireUser();
if (user.role !== "admin") location.replace("/");
document.getElementById("admin-name").textContent = user.full_name;
document.getElementById("logout").addEventListener("click", logout);
