// Typed API client — the mobile app talks ONLY to the FastAPI backend.
// It never calls Groq, Supabase, or the database directly (Principle IV).
// Provider/language preferences travel as headers (see store.ts); the backend
// holds all credentials except a user's own optional Groq key.

import { settingsHeaders } from "../store";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE ?? "http://localhost:8000";
console.log("[API_BASE]", API_BASE);

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
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
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`${API_BASE}${path}`, { headers: settingsHeaders() }));
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...settingsHeaders() },
      body: JSON.stringify(body),
    })
  );
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  return handle<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: settingsHeaders(),
      body: form,
    })
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return handle<T>(
    await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: settingsHeaders() })
  );
}

export { API_BASE };
