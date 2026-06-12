// Settings: appearance (light/dark), UI language, AI provider — cloud Groq
// (app key), cloud Groq with the user's own key, or fully local via Ollama —
// plus the help & guide entry. Choices apply immediately; client.ts attaches
// provider/language as headers on every call.

import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Card, Chip } from "../components/UI";
import { LANGUAGE_OPTIONS, useT } from "../i18n";
import type { RootStackParamList } from "../navigation";
import { fonts, radius, useTheme } from "../theme";
import { updateSettings, useSettings, type LLMProvider } from "../store";

type Nav = NativeStackNavigationProp<RootStackParamList, "Settings">;

export function SettingsScreen() {
  const s = useSettings();
  const t = useT();
  const { c } = useTheme();
  const navigation = useNavigation<Nav>();

  const providers: { id: LLMProvider; label: string }[] = [
    { id: "default", label: t("providerDefault") },
    { id: "groq-byok", label: t("providerByok") },
    { id: "ollama", label: t("providerOllama") },
  ];

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={styles.container}>
      <Card style={styles.card}>
        <Text style={[styles.section, { color: c.text }]}>{t("appearance")}</Text>
        <View style={styles.rowWrap}>
          <ThemeOption
            icon="sunny-outline"
            label={t("themeLight")}
            active={s.theme === "light"}
            onPress={() => updateSettings({ theme: "light" })}
          />
          <ThemeOption
            icon="moon-outline"
            label={t("themeDark")}
            active={s.theme === "dark"}
            onPress={() => updateSettings({ theme: "dark" })}
          />
        </View>
      </Card>

      <Card style={styles.card}>
        <Text style={[styles.section, { color: c.text }]}>{t("language")}</Text>
        <View style={styles.rowWrap}>
          {LANGUAGE_OPTIONS.map((opt) => (
            <Chip
              key={opt.code}
              label={opt.label}
              active={s.language === opt.code}
              onPress={() => updateSettings({ language: opt.code })}
            />
          ))}
        </View>
      </Card>

      <Card style={styles.card}>
        <Text style={[styles.section, { color: c.text }]}>{t("aiProvider")}</Text>
        <View style={styles.colGap}>
          {providers.map((p) => (
            <Chip
              key={p.id}
              label={p.label}
              active={s.provider === p.id}
              onPress={() => updateSettings({ provider: p.id })}
            />
          ))}
        </View>

        {s.provider === "groq-byok" && (
          <View style={styles.field}>
            <Text style={[styles.label, { color: c.text }]}>{t("groqKeyLabel")}</Text>
            <TextInput
              style={[styles.input, { backgroundColor: c.well, borderColor: c.line, color: c.text }]}
              value={s.groqKey}
              onChangeText={(v) => updateSettings({ groqKey: v })}
              placeholder="gsk_…"
              placeholderTextColor={c.muted}
              autoCapitalize="none"
              secureTextEntry
            />
          </View>
        )}

        {s.provider === "ollama" && (
          <>
            <View style={styles.field}>
              <Text style={[styles.label, { color: c.text }]}>{t("ollamaUrlLabel")}</Text>
              <TextInput
                style={[styles.input, { backgroundColor: c.well, borderColor: c.line, color: c.text }]}
                value={s.ollamaUrl}
                onChangeText={(v) => updateSettings({ ollamaUrl: v })}
                placeholder="http://192.168.x.x:11434"
                placeholderTextColor={c.muted}
                autoCapitalize="none"
              />
            </View>
            <View style={styles.field}>
              <Text style={[styles.label, { color: c.text }]}>{t("ollamaModelLabel")}</Text>
              <TextInput
                style={[styles.input, { backgroundColor: c.well, borderColor: c.line, color: c.text }]}
                value={s.ollamaModel}
                onChangeText={(v) => updateSettings({ ollamaModel: v })}
                placeholder="llama3.2"
                placeholderTextColor={c.muted}
                autoCapitalize="none"
              />
            </View>
          </>
        )}

        <Text style={[styles.note, { color: c.muted }]}>{t("settingsNote")}</Text>
      </Card>

      <Pressable
        onPress={() => navigation.navigate("Help")}
        style={({ pressed }) => [
          styles.helpRow,
          { backgroundColor: c.card, borderColor: c.line },
          pressed && { opacity: 0.8 },
        ]}
      >
        <View style={[styles.helpIcon, { backgroundColor: c.accentSoft }]}>
          <Ionicons name="help-circle-outline" size={22} color={c.accent} />
        </View>
        <Text style={[styles.helpText, { color: c.text }]}>{t("helpLink")}</Text>
        <Ionicons name="chevron-forward" size={18} color={c.muted} />
      </Pressable>
    </ScrollView>
  );
}

function ThemeOption({
  icon,
  label,
  active,
  onPress,
}: {
  icon: "sunny-outline" | "moon-outline";
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  const { c } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.themeOpt,
        { borderColor: active ? c.accent : c.line, backgroundColor: active ? c.accentSoft : c.card },
        pressed && { opacity: 0.8 },
      ]}
    >
      <Ionicons name={icon} size={18} color={active ? c.accent : c.muted} />
      <Text style={[styles.themeOptText, { color: active ? c.accentDeep : c.muted }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { padding: 14, gap: 12, paddingBottom: 28 },
  card: { gap: 10 },
  section: { fontSize: 15, fontFamily: fonts.bodyHeavy },
  rowWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  colGap: { gap: 8, alignItems: "flex-start" },
  field: { gap: 4, marginTop: 6 },
  label: { fontFamily: fonts.bodySemi, fontSize: 13.5 },
  input: { borderWidth: 1, borderRadius: 8, padding: 9, fontFamily: fonts.body },
  note: { fontSize: 12.5, lineHeight: 18, marginTop: 8, fontFamily: fonts.body },
  themeOpt: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderWidth: 1.5,
    borderRadius: radius.md,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  themeOptText: { fontFamily: fonts.bodyBold, fontSize: 14 },
  helpRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 14,
  },
  helpIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  helpText: { flex: 1, fontFamily: fonts.bodyBold, fontSize: 15 },
});
