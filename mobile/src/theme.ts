// Shared visual language for all screens (mirrors the web page's accent).
import type { ViewStyle } from "react-native";

export const colors = {
  bg: "#f6f7fb",
  card: "#ffffff",
  line: "#e5e9f2",
  text: "#0f172a",
  muted: "#64748b",
  accent: "#2563eb",
  accentDeep: "#4f46e5",
  accentSoft: "#e4ebfd",
  good: "#059669",
  goodSoft: "#d1fae5",
  warn: "#b45309",
  warnSoft: "#fef3c7",
  danger: "#dc2626",
  dangerSoft: "#fee2e2",
};

export const radius = { sm: 8, md: 12, lg: 16, xl: 24 };

// One soft elevation used by every raised surface (iOS shadow + Android elevation).
export const shadow: ViewStyle = {
  shadowColor: "#0f172a",
  shadowOpacity: 0.07,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 4 },
  elevation: 3,
};

// Hero / brand gradient (indigo → blue → sky), shared with the web header.
export const heroGradient = ["#4f46e5", "#2563eb", "#0ea5e9"] as const;

export const SEED_CATEGORIES = [
  "Telecom/Recharge",
  "Groceries",
  "Utilities",
  "Food & Dining",
  "Shopping",
  "Other",
];
