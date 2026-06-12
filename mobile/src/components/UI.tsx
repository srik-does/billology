// Small shared UI primitives so every screen speaks the same visual language.
// Each primitive reads the active palette via useTheme(), so the whole set
// restyles instantly when the light/dark toggle flips.
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { fonts, radius, shadowFor, useTheme } from "../theme";

type BtnProps = {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  busy?: boolean;
  style?: StyleProp<ViewStyle>;
  icon?: keyof typeof Ionicons.glyphMap;
};

export function Btn({ title, onPress, variant = "primary", disabled, busy, style, icon }: BtnProps) {
  const { c, mode } = useTheme();
  const palette = {
    primary: { bg: c.accent, fg: c.onAccent, border: c.accent },
    secondary: { bg: c.card, fg: c.accent, border: c.accentSoft },
    danger: { bg: c.card, fg: c.danger, border: c.dangerSoft },
  }[variant];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        styles.btn,
        variant === "primary" && shadowFor(mode),
        { backgroundColor: palette.bg, borderColor: palette.border },
        (disabled || busy) && { opacity: 0.5 },
        pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={palette.fg} size="small" />
      ) : (
        <View style={styles.btnInner}>
          {icon ? <Ionicons name={icon} size={17} color={palette.fg} /> : null}
          <Text style={[styles.btnText, { color: palette.fg }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const { c, mode } = useTheme();
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: c.card, borderColor: c.line },
        shadowFor(mode),
        style,
      ]}
    >
      {children}
    </View>
  );
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
  const { c } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        { borderColor: c.line, backgroundColor: c.card },
        active && { backgroundColor: c.accent, borderColor: c.accent },
        pressed && { opacity: 0.8 },
      ]}
    >
      <Text style={[styles.chipText, { color: active ? c.onAccent : c.muted }]}>{label}</Text>
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
  active,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  active?: boolean;
}) {
  const { c, mode } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.tile,
        { backgroundColor: c.card, borderColor: active ? c.accent : c.line },
        shadowFor(mode),
        disabled && { opacity: 0.5 },
        pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 },
        style,
      ]}
    >
      <View style={[styles.tileIcon, { backgroundColor: c.accentSoft }]}>
        <Ionicons name={icon} size={24} color={c.accent} />
      </View>
      <Text style={[styles.tileLabel, { color: c.text }]} numberOfLines={2}>
        {label}
      </Text>
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
  const { c } = useTheme();
  const palette = {
    info: { bg: c.accentSoft, fg: c.accentDeep, icon: "information-circle" as const },
    warn: { bg: c.warnSoft, fg: c.warn, icon: "alert-circle" as const },
    error: { bg: c.dangerSoft, fg: c.danger, icon: "close-circle" as const },
  }[kind];
  return (
    <View style={[styles.banner, { backgroundColor: palette.bg }]}>
      <Ionicons name={palette.icon} size={17} color={palette.fg} style={{ marginTop: 1 }} />
      <Text style={[styles.bannerText, { color: palette.fg }]}>{text}</Text>
    </View>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  const { c } = useTheme();
  return <Text style={[styles.sectionTitle, { color: c.muted }]}>{children}</Text>;
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
  btnInner: { flexDirection: "row", alignItems: "center", gap: 8 },
  btnText: { fontFamily: fonts.bodyBold, fontSize: 15 },
  card: {
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 16,
  },
  chip: {
    paddingVertical: 7,
    paddingHorizontal: 13,
    borderRadius: 18,
    borderWidth: 1,
  },
  chipText: { fontSize: 13, fontFamily: fonts.bodySemi },
  tile: {
    flex: 1,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: 18,
    paddingHorizontal: 8,
    alignItems: "center",
    gap: 10,
  },
  tileIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  tileLabel: { fontFamily: fonts.bodyBold, fontSize: 13.5, textAlign: "center" },
  banner: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    borderRadius: radius.md,
    alignItems: "flex-start",
  },
  bannerText: { flex: 1, fontSize: 13.5, lineHeight: 19, fontFamily: fonts.bodySemi },
  sectionTitle: {
    fontSize: 13,
    fontFamily: fonts.bodyBold,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 6,
  },
});
