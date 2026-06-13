// Typed API client — the mobile app talks ONLY to the FastAPI backend.
// It never calls Groq, Supabase, or the database directly (Principle IV).
// Provider/language preferences travel as headers (see store.ts); the backend
// holds all credentials except a user's own optional Groq key.

import { getAccessToken } from "../auth";
import { settingsHeaders } from "../store";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE ?? "http://localhost:8000";
console.log("[API_BASE]", API_BASE);

// Settings/language headers plus the signed-in user's bearer token. The backend
// requires the token on every bill/dashboard/Q&A route and scopes data to the
// user via it (RLS), so this rides on every request.
function authedHeaders(): Record<string, string> {
  const headers = settingsHeaders();
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const GATEWAY_STATUS = new Set([502, 503, 504]);

// Free hosting (Render's free tier) sleeps the backend after ~15 min idle.
// The first requests during wake-up come back as a 502/503/504 from the edge
// proxy with an EMPTY body, or as an outright network error — which surfaced
// to the user as a bare "ApiError". fetchResilient retries those transparently
// with backoff so a cold open just takes a little longer instead of failing.
// An app-level 502 (e.g. a save/persist failure) carries a JSON body and is a
// real error, so it is returned to the caller and never retried. Non-idempotent
// calls (saving a bill) pass retries=0 to avoid any double-submit on a dropped
// connection.
async function fetchResilient(path: string, init: RequestInit, retries = 9): Promise<Response> {
  let delay = 1500;
  for (let attempt = 0; ; attempt++) {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}${path}`, init);
    } catch (netErr) {
      // Connection refused/reset — typical of the very first hit on a cold service.
      if (attempt >= retries) throw netErr;
      await sleep(delay);
      delay = Math.min(delay * 1.6, 8000);
      continue;
    }
    if (GATEWAY_STATUS.has(res.status) && attempt < retries) {
      // Only retry a true edge wake-up: empty or non-JSON body. An app 502
      // (JSON {error, detail}) is a real failure and must reach the caller.
      const text = await res.clone().text();
      if (!text.trim() || !text.trim().startsWith("{")) {
        await sleep(delay);
        delay = Math.min(delay * 1.6, 8000);
        continue;
      }
    }
    return res;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      // `reason` carries the friendly decline message (422 {declined, reason})
      // — e.g. the PDF page-cap text — and must win over generic codes.
      detail = body?.reason ?? body?.detail ?? body?.error ?? detail;
    } catch {
      // Empty/non-JSON error body. A gateway code here means the server never
      // produced a response (still waking, or timed out) — say so plainly
      // instead of leaving a bare status code.
      if (GATEWAY_STATUS.has(res.status)) {
        detail = "The server is starting up. Please wait a few seconds and try again.";
      }
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetchResilient(path, { headers: authedHeaders() }));
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetchResilient(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authedHeaders() },
      body: JSON.stringify(body),
    })
  );
}

export async function apiPostForm<T>(path: string, form: FormData, retries = 9): Promise<T> {
  return handle<T>(
    await fetchResilient(
      path,
      { method: "POST", headers: authedHeaders(), body: form },
      retries
    )
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return handle<T>(
    await fetchResilient(path, { method: "DELETE", headers: authedHeaders() })
  );
}

export { API_BASE };
