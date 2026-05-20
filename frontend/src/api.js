// Thin wrapper over the backend.
// - Local dev: BASE = '/api', proxied to the backend by Vite (vite.config.js).
// - Production: either keep '/api' and let a host rewrite forward it to the
//   backend (see frontend/vercel.json), or set VITE_API_BASE to the backend URL
//   at build time to call it directly (backend CORS must then allow this origin).
const BASE = import.meta.env.VITE_API_BASE || '/api';

async function postFile(path, file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json();
}

export const uploadTitles = (file) => postFile('/upload/titles', file);
export const uploadTraits = (file) => postFile('/upload/traits', file);
export const uploadDeaths = (file) => postFile('/upload/deaths', file);
export const uploadNames = (file) => postFile('/upload/names', file);
export const uploadReligions = (file) => postFile('/upload/religions', file);
export const uploadSecrets = (file) => postFile('/upload/secrets', file);
export const uploadCultures = (file) => postFile('/upload/cultures', file);

export async function startGeneration(payload) {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`generate failed (${res.status})`);
  return res.json();
}

export async function fetchStatus(taskId) {
  const res = await fetch(`${BASE}/status/${taskId}`);
  if (!res.ok) throw new Error(`status failed (${res.status})`);
  return res.json();
}

export const downloadUrl = (taskId) => `${BASE}/download/${taskId}`;

export async function fetchTree(taskId) {
  const res = await fetch(`${BASE}/result/${taskId}/tree`);
  if (!res.ok) throw new Error(`Tree fetch failed (${res.status})`);
  return res.json();
}
