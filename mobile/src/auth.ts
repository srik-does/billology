// Authentication: Google sign-in via Supabase Auth.
//
// The app signs in with Google through Supabase, gets a session (a JWT), and
// sends that token as `Authorization: Bearer` on every backend call (see
// api/client.ts). The backend verifies it and scopes all data to this user via
// Postgres RLS — one user never sees another's bills. The client still talks
// ONLY to our backend for bill data (Principle IV); Supabase is used here just
// for the identity handshake.
//
// Uses the OAuth implicit flow (tokens returned in the redirect URL) so no
// native PKCE/crypto polyfill is needed in Expo. Session is persisted in
// AsyncStorage and auto-refreshed.

import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, type Session } from "@supabase/supabase-js";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { useSyncExternalStore } from "react";

WebBrowser.maybeCompleteAuthSession();

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.warn(
    "[auth] EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_ANON_KEY are not set — sign-in will fail."
  );
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    // We handle the redirect ourselves (no web URL detection in RN).
    detectSessionInUrl: false,
    flowType: "implicit",
  },
});

// --- session store (useSyncExternalStore, mirrors store.ts) -----------------

type AuthState = { session: Session | null; loading: boolean };
let state: AuthState = { session: null, loading: true };
const listeners = new Set<() => void>();

function setState(patch: Partial<AuthState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

// Restore any persisted session on startup, then keep in sync with auth events.
supabase.auth.getSession().then(({ data }) => {
  setState({ session: data.session, loading: false });
});
supabase.auth.onAuthStateChange((_event, session) => {
  setState({ session, loading: false });
});

export function useAuth(): AuthState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state
  );
}

/** Current access token (JWT) for the Authorization header, or null. */
export function getAccessToken(): string | null {
  return state.session?.access_token ?? null;
}

/** The signed-in user's email, for display. */
export function getUserEmail(): string | null {
  return state.session?.user?.email ?? null;
}

// --- sign-in / sign-out -----------------------------------------------------

/** Pull access/refresh tokens out of the redirect URL (query or #fragment). */
function tokensFromUrl(url: string): { access_token?: string; refresh_token?: string; error?: string } {
  const out: Record<string, string> = {};
  const tail = url.split(/[#?]/).slice(1).join("&");
  for (const pair of tail.split("&")) {
    const [k, v] = pair.split("=");
    if (k && v) out[decodeURIComponent(k)] = decodeURIComponent(v);
  }
  return {
    access_token: out.access_token,
    refresh_token: out.refresh_token,
    error: out.error_description || out.error,
  };
}

/**
 * Launch the Google sign-in flow. Resolves once a session is established (or
 * throws on failure / returns silently if the user cancels).
 */
export async function signInWithGoogle(): Promise<void> {
  const redirectTo = AuthSession.makeRedirectUri({ scheme: "billology" });

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo, skipBrowserRedirect: true },
  });
  if (error) throw error;
  if (!data?.url) throw new Error("Could not start Google sign-in.");

  const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
  if (result.type !== "success") return; // user dismissed the browser

  const { access_token, refresh_token, error: oauthError } = tokensFromUrl(result.url);
  if (oauthError) throw new Error(oauthError);
  if (!access_token || !refresh_token) throw new Error("Sign-in did not return a session.");

  const { error: sessionError } = await supabase.auth.setSession({ access_token, refresh_token });
  if (sessionError) throw sessionError;
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}
