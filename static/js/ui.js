export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => document.querySelectorAll(sel);

export function showToast(msg, type = 'error') {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast toast-${type} show`;
  setTimeout(() => t.classList.remove('show'), 4000);
}

export function showLoading(text = '處理中...') {
  const loadingText = $('#loading-text');
  const overlay = $('#loading-overlay');
  if (loadingText) loadingText.textContent = text;
  if (overlay) overlay.classList.add('show');
}

export function hideLoading() {
  $('#loading-overlay')?.classList.remove('show');
}

export function isMobileViewport() {
  return window.matchMedia('(max-width: 768px)').matches;
}

function setSidebarOpen(open) {
  $('#sidebar')?.classList.toggle('open', open);
  $('#sidebar-backdrop')?.classList.toggle('show', open);
  document.body.classList.toggle('sidebar-open', open);
}

export function toggleSidebar() {
  setSidebarOpen(!$('#sidebar')?.classList.contains('open'));
}

export function closeSidebar() {
  setSidebarOpen(false);
}

export function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
