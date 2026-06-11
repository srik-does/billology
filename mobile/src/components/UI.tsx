// Small shared UI primitives so every screen speaks the same visual language.
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, ViewStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, shadow } from "../theme";

type BtnProps = {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  busy?: boolean;
  style?: ViewStyle;
};

export function Btn({ title, onPress, variant = "primary", disabled, busy, style }: BtnProps) {
  const palette = {
    primary: { bg: colors.accent, fg: "#ffffff", border: colors.accent },
    secondary: { bg: colors.card, fg: colors.accent, border: colors.accentSoft },
    danger: { bg: colors.card, fg: colors.danger, border: colors.dangerSoft },
  }[variant];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        styles.btn,
        variant === "primary" && shadow,
        { backgroundColor: palette.bg, borderColor: palette.border },
        (disabled || busy) && { opacity: 0.5 },
        pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={palette.fg} size="small" />
      ) : (
        <Text style={[styles.btnText, { color: palette.fg }]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active && { backgroundColor: colors.accent, borderColor: colors.accent },
        pressed && { opacity: 0.8 },
      ]}
    >
      <Text style={[styles.chipText, active && { color: "#ffffff" }]}>{label}</Text>
    </Pressable>
  );
}

/** Large tappable action (icon in a soft circle + label) for primary flows. */
export function ActionTile({
  icon,
  label,
  onPress,
  disabled,
  style,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  disabled?: boolean;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.tile,
        shadow,
        disabled && { opacity: 0.5 },
        pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 },
        style,
      ]}
    >
      <View style={styles.tileIcon}>
        <Ionicons name={icon} size={24} color={colors.accent} />
      </View>
      <Text style={styles.tileLabel}>{label}</Text>
    </Pressable>
  );
}

/** Inline status banner — the smooth replacement for raw warning text. */
export function Banner({
  kind = "info",
  text,
}: {
  kind?: "info" | "warn" | "error";
  text: string;
}) {
  const palette = {
    info: { bg: colors.accentSoft, fg: colors.accent, icon: "information-circle" as const },
    warn: { bg: colors.warnSoft, fg: colors.warn, icon: "alert-circle" as const },
    error: { bg: colors.dangerSoft, fg: colors.danger, icon: "close-circle" as const },
  }[kind];
  return (
    <View style={[styles.banner, { backgroundColor: palette.bg }]}>
      <Ionicons name={palette.icon} size={17} color={palette.fg} style={{ marginTop: 1 }} />
      <Text style={[styles.bannerText, { color: palette.fg }]}>{text}</Text>
    </View>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

const styles = StyleSheet.create({
  btn: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: radius.md,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 46,
  },
  btnText: { fontWeight: "700", fontSize: 15 },
  card: {
    backgroundColor: colors.card,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 16,
    ...shadow,
  },
  chip: {
    paddingVertical: 7,
    paddingHorizontal: 13,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.card,
  },
  chipText: { fontSize: 13, color: colors.muted, fontWeight: "600" },
  tile: {
    flex: 1,
    backgroundColor: colors.card,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: 18,
    alignItems: "center",
    gap: 10,
  },
  tileIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  tileLabel: { fontWeight: "700", fontSize: 14, color: colors.text },
  banner: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    borderRadius: radius.md,
    alignItems: "flex-start",
  },
  bannerText: { flex: 1, fontSize: 13.5, lineHeight: 19, fontWeight: "600" },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 6,
  },
});
