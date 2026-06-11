// Typed API client — the mobile app talks ONLY to the FastAPI backend.
// It never calls Groq, Supabase, or the database directly (Principle IV).

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
      detail = body?.error ?? body?.detail ?? detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`${API_BASE}${path}`));
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  return handle<T>(
    await fetch(`${API_BASE}${path}`, { method: "POST", body: form })
  );
}

export { API_BASE };
