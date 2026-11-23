import { requireAdmin } from "../auth.js";
import { initTelegram } from "../telegram.js";

// Admin bosh sahifasi hozircha birinchi admin bo'limiga yo'naltiradi.
initTelegram();
await requireAdmin();
location.replace("/admin/orders.html");
