const LOCAL = new Set(['localhost', '127.0.0.1', '::1']);
export const API_BASE = LOCAL.has(window.location.hostname) ? window.location.origin : window.location.origin;

export function getApiKey() {
  let k = localStorage.getItem('secaudit_api_key');
  if (!k) {
    k = prompt('請輸入 SecAudit API Key（即 .env 中的 SECAUDIT_API_KEY）：') || '';
    if (k) localStorage.setItem('secaudit_api_key', k);
  }
  return k;
}

export function resetApiKey() {
  localStorage.removeItem('secaudit_api_key');
}

export function getAuditorName() { return localStorage.getItem('secaudit_auditor') || ''; }
export function setAuditorName(n) { localStorage.setItem('secaudit_auditor', n.trim()); }

export async function api(method, path, body) {
  const opts = { method, headers: { 'X-API-Key': getApiKey() } };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}/api${path}`, opts);
  if (res.status === 401) {
    resetApiKey();
    const newKey = getApiKey();
    if (newKey) {
      opts.headers['X-API-Key'] = newKey;
      const retry = await fetch(`${API_BASE}/api${path}`, opts);
      if (!retry.ok) throw new Error(await retry.text() || `HTTP ${retry.status}`);
      return retry.json();
    }
  }
  if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
  return res.json();
}

export async function uploadApi(path, formData) {
  const res = await fetch(`${API_BASE}/api${path}`, {
    method: 'POST',
    headers: { 'X-API-Key': getApiKey() },
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
  return res.json();
}

export function openSSE(projectId, format, { onChunk, onRepair, onDone, onError }) {
  const url = `${API_BASE}/api/projects/${projectId}/findings/stream?format=${format}&api_key=${encodeURIComponent(getApiKey())}`;
  const src = new EventSource(url);
  src.onmessage = (e) => {
    if (e.data === '[DONE]') { src.close(); onDone(); return; }
    try {
      const d = JSON.parse(e.data);
      if (d.repair) onRepair(d.repair);
      else onChunk(d.chunk || '');
    } catch (_) {}
  };
  src.onerror = () => { src.close(); onError(); };
}
