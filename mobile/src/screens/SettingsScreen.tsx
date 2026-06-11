// Settings: UI language (English/Hindi/Telugu) and AI provider — cloud Groq
// (app key), cloud Groq with the user's own key, or fully local via Ollama.
// Choices apply immediately; client.ts attaches them as headers on every call.

import { ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { Card, Chip } from "../components/UI";
import { LANGUAGE_OPTIONS, useT } from "../i18n";
import { colors } from "../theme";
import { updateSettings, useSettings, type LLMProvider } from "../store";

export function SettingsScreen() {
  const s = useSettings();
  const t = useT();

  const providers: { id: LLMProvider; label: string }[] = [
    { id: "default", label: t("providerDefault") },
    { id: "groq-byok", label: t("providerByok") },
    { id: "ollama", label: t("providerOllama") },
  ];

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.container}>
      <Card style={styles.card}>
        <Text style={styles.section}>{t("language")}</Text>
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
        <Text style={styles.section}>{t("aiProvider")}</Text>
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
            <Text style={styles.label}>{t("groqKeyLabel")}</Text>
            <TextInput
              style={styles.input}
              value={s.groqKey}
              onChangeText={(v) => updateSettings({ groqKey: v })}
              placeholder="gsk_…"
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
              secureTextEntry
            />
          </View>
        )}

        {s.provider === "ollama" && (
          <>
            <View style={styles.field}>
              <Text style={styles.label}>{t("ollamaUrlLabel")}</Text>
              <TextInput
                style={styles.input}
                value={s.ollamaUrl}
                onChangeText={(v) => updateSettings({ ollamaUrl: v })}
                placeholder="http://192.168.x.x:11434"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
              />
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>{t("ollamaModelLabel")}</Text>
              <TextInput
                style={styles.input}
                value={s.ollamaModel}
                onChangeText={(v) => updateSettings({ ollamaModel: v })}
                placeholder="llama3.2"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
              />
            </View>
          </>
        )}

        <Text style={styles.note}>{t("settingsNote")}</Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { backgroundColor: colors.bg },
  container: { padding: 14, gap: 12 },
  card: { gap: 10 },
  section: { fontSize: 15, fontWeight: "700", color: colors.text },
  rowWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  colGap: { gap: 8, alignItems: "flex-start" },
  field: { gap: 4, marginTop: 6 },
  label: { fontWeight: "600", color: colors.text, fontSize: 13.5 },
  input: {
    backgroundColor: colors.bg,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 8,
    padding: 9,
    color: colors.text,
  },
  note: { color: colors.muted, fontSize: 12.5, lineHeight: 18, marginTop: 8 },
});
