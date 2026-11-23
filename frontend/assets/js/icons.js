// Ikonkalar: o'zgarmas SVG (foydalanuvchi matni yo'q), shuning uchun innerHTML xavfsiz.

const PATHS = {
  menu: '<path d="M4 11h16M5 11a7 7 0 0 1 14 0M3 15h18M7 19h10" />',
  bag: '<path d="M6 8h12l-1 12H7L6 8Z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" />',
  receipt: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" /><path d="M9 8h6M9 12h6M9 16h4" />',
  plus: '<path d="M12 5v14M5 12h14" />',
  minus: '<path d="M5 12h14" />',
  cash: '<rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M6 9v.01M18 15v.01" />',
  card: '<rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h4" />',
};

export function icon(name) {
  const span = document.createElement("span");
  span.className = "icon";
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${PATHS[name]}</svg>`;
  return span;
}
