// Shared visual language for all screens — "paper & ink" identity.
// Warm receipt-paper neutrals, emerald-teal primary, saffron-gold accent;
// a full dark variant mirrors every token. Screens read the active palette
// through useTheme() and build their styles per render, so toggling the
// theme restyles the whole app instantly.

import { createContext, useContext } from "react";
import type { TextStyle, ViewStyle } from "react-native";

export type Palette = {
  bg: string;
  card: string;
  /** Slightly recessed surface (inputs, tracks) sitting on a card. */
  well: string;
  line: string;
  text: string;
  muted: string;
  accent: string;
  accentDeep: string;
  accentSoft: string;
  onAccent: string;
  gold: string;
  goldSoft: string;
  good: string;
  goodSoft: string;
  warn: string;
  warnSoft: string;
  danger: string;
  dangerSoft: string;
  /** Hero / brand gradient stops. */
  hero: readonly [string, string, string];
  /** Categorical series for charts. */
  series: string[];
};

export const palettes: Record<"light" | "dark", Palette> = {
  light: {
    bg: "#F6F3EC",
    card: "#FFFFFF",
    well: "#F3EFE6",
    line: "#E6E0D2",
    text: "#1F1B16",
    muted: "#7C7468",
    accent: "#0F766E",
    accentDeep: "#115E59",
    accentSoft: "#DDEEE9",
    onAccent: "#FFFFFF",
    gold: "#B45309",
    goldSoft: "#FBEED7",
    good: "#047857",
    goodSoft: "#D7F0E4",
    warn: "#B45309",
    warnSoft: "#FBEED7",
    danger: "#C2410C",
    dangerSoft: "#FBE3D4",
    hero: ["#134E4A", "#0F766E", "#3B8C5E"] as const,
    series: ["#0F766E", "#D97706", "#7C5CBF", "#C2410C", "#2563EB", "#047857", "#9A8C7A"],
  },
  dark: {
    bg: "#161310",
    card: "#211D18",
    well: "#1A1713",
    line: "#373027",
    text: "#F1ECE2",
    muted: "#A89E8F",
    accent: "#3BBFAD",
    accentDeep: "#2DA796",
    accentSoft: "#173B36",
    onAccent: "#0C1311",
    gold: "#E9A23B",
    goldSoft: "#3A2D14",
    good: "#43C695",
    goodSoft: "#143527",
    warn: "#E9A23B",
    warnSoft: "#3A2D14",
    danger: "#F08C5A",
    dangerSoft: "#3D2114",
    hero: ["#0D2B28", "#11463F", "#1C5A40"] as const,
    series: ["#3BBFAD", "#E9A23B", "#A78BFA", "#F08C5A", "#60A5FA", "#43C695", "#8C8273"],
  },
};

export type ThemeMode = "light" | "dark";

export type Theme = {
  mode: ThemeMode;
  c: Palette;
  toggle: () => void;
};

export const ThemeContext = createContext<Theme>({
  mode: "light",
  c: palettes.light,
  toggle: () => {},
});

export function useTheme(): Theme {
  return useContext(ThemeContext);
}

export const radius = { sm: 8, md: 12, lg: 16, xl: 24 };

// Typography: Fraunces (display serif — wordmark, headings, amounts) and
// Manrope (body). Indic scripts fall through to the system font per glyph.
export const fonts = {
  display: "Fraunces_700Bold",
  displayItalic: "Fraunces_700Bold_Italic",
  body: "Manrope_500Medium",
  bodySemi: "Manrope_600SemiBold",
  bodyBold: "Manrope_700Bold",
  bodyHeavy: "Manrope_800ExtraBold",
};

export const type: Record<string, TextStyle> = {
  display: { fontFamily: fonts.display, letterSpacing: 0.2 },
  heading: { fontFamily: fonts.bodyHeavy, letterSpacing: 0.2 },
  body: { fontFamily: fonts.body },
  semi: { fontFamily: fonts.bodySemi },
  bold: { fontFamily: fonts.bodyBold },
};

// One soft elevation used by every raised surface (iOS shadow + Android elevation).
export function shadowFor(mode: ThemeMode): ViewStyle {
  return {
    shadowColor: mode === "light" ? "#3D3528" : "#000000",
    shadowOpacity: mode === "light" ? 0.08 : 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  };
}

export const SEED_CATEGORIES = [
  "Telecom/Recharge",
  "Groceries",
  "Utilities",
  "Food & Dining",
  "Shopping",
  "Other",
];
