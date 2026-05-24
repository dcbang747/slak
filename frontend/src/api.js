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

// Runs the whole generation in one request and returns
// { characters, titles_with_history, family_tree, zip_b64 }.
export async function startGeneration(payload) {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch { /* ignore */ }
    throw new Error(`generate failed (${res.status})${detail ? `: ${detail}` : ''}`);
  }
  return res.json();
}

// Jamie's Handy Character History Generator (linear single-dynasty mode).
// Same response shape as startGeneration.
export async function startJamieGeneration(payload) {
  const res = await fetch(`${BASE}/generate_jamie`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch { /* ignore */ }
    throw new Error(`generate failed (${res.status})${detail ? `: ${detail}` : ''}`);
  }
  return res.json();
}

// Turn the base64 ZIP from /generate into a downloadable object URL.
export function zipBlobUrl(zipB64) {
  const bytes = Uint8Array.from(atob(zipB64), (c) => c.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
}
