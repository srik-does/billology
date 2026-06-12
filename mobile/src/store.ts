// App settings: UI language + LLM provider choice (local Ollama / cloud Groq /
// bring-your-own-key). Plain module store with useSyncExternalStore so screens
// re-render on change; client.ts reads the snapshot to build request headers.

import { useSyncExternalStore } from "react";
import { Appearance } from "react-native";

export type Language =
  | "en" | "hi" | "te" | "ta" | "kn" | "ml" | "bn"
  | "mr" | "gu" | "pa" | "or" | "as" | "ur";
export type LLMProvider = "default" | "groq-byok" | "ollama";
export type ThemeSetting = "light" | "dark";

export type AppSettings = {
  language: Language;
  provider: LLMProvider;
  groqKey: string;
  ollamaUrl: string;
  ollamaModel: string;
  theme: ThemeSetting;
};

let settings: AppSettings = {
  language: "en",
  provider: "default",
  groqKey: "",
  ollamaUrl: "http://localhost:11434",
  ollamaModel: "llama3.2",
  // Start from the device's appearance; the in-app toggle takes over from there.
  theme: Appearance.getColorScheme() === "dark" ? "dark" : "light",
};

const listeners = new Set<() => void>();

export function getSettings(): AppSettings {
  return settings;
}

export function updateSettings(patch: Partial<AppSettings>) {
  settings = { ...settings, ...patch };
  listeners.forEach((l) => l());
}

export function useSettings(): AppSettings {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => settings
  );
}

// --- One-shot signal: a bill was just saved ---------------------------------
// Review fires it; the Capture screen listens and clears its analyzed
// candidate so the home screen comes back fresh after a save.
let saveCounter = 0;
const saveListeners = new Set<() => void>();

export function markBillSaved() {
  saveCounter++;
  saveListeners.forEach((l) => l());
}

export function useBillSavedCounter(): number {
  return useSyncExternalStore(
    (cb) => {
      saveListeners.add(cb);
      return () => saveListeners.delete(cb);
    },
    () => saveCounter
  );
}

// Headers consumed by the backend's request-context middleware.
export function settingsHeaders(): Record<string, string> {
  const h: Record<string, string> = { "X-Language": settings.language };
  if (settings.provider === "ollama") {
    h["X-LLM-Provider"] = "ollama";
    if (settings.ollamaUrl) h["X-Ollama-Url"] = settings.ollamaUrl;
    if (settings.ollamaModel) h["X-Ollama-Model"] = settings.ollamaModel;
  } else if (settings.provider === "groq-byok" && settings.groqKey) {
    h["X-LLM-Provider"] = "groq";
    h["X-Groq-Key"] = settings.groqKey;
  }
  return h;
}
