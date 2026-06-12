// Help & guide (#9): a step-by-step walkthrough of the whole app, written for
// a first-time user. Pure content — numbered steps with icons, plus the
// privacy/provider note.

import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Card } from "../components/UI";
import { useT, type TKey } from "../i18n";
import { fonts, useTheme } from "../theme";

const STEPS: { icon: keyof typeof Ionicons.glyphMap; title: TKey; body: TKey }[] = [
  { icon: "camera-outline", title: "h1t", body: "h1b" },
  { icon: "shield-checkmark-outline", title: "h2t", body: "h2b" },
  { icon: "create-outline", title: "h3t", body: "h3b" },
  { icon: "receipt-outline", title: "h4t", body: "h4b" },
  { icon: "pie-chart-outline", title: "h5t", body: "h5b" },
  { icon: "chatbubbles-outline", title: "h6t", body: "h6b" },
];

export function HelpScreen() {
  const t = useT();
  const { c } = useTheme();

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={styles.container}>
      <Text style={[styles.intro, { color: c.muted }]}>{t("helpIntro")}</Text>

      {STEPS.map((step, i) => (
        <Card key={step.title} style={styles.step}>
          <View style={styles.stepHead}>
            <View style={[styles.stepNum, { backgroundColor: c.accent }]}>
              <Text style={[styles.stepNumText, { color: c.onAccent }]}>{i + 1}</Text>
            </View>
            <Ionicons name={step.icon} size={20} color={c.accent} />
            <Text style={[styles.stepTitle, { color: c.text }]}>{t(step.title)}</Text>
          </View>
          <Text style={[styles.stepBody, { color: c.muted }]}>{t(step.body)}</Text>
        </Card>
      ))}

      <Card style={[styles.step, { borderColor: c.goldSoft }]}>
        <View style={styles.stepHead}>
          <Ionicons name="lock-closed-outline" size={20} color={c.gold} />
          <Text style={[styles.stepTitle, { color: c.text }]}>{t("helpPrivacyT")}</Text>
        </View>
        <Text style={[styles.stepBody, { color: c.muted }]}>{t("helpPrivacyB")}</Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12, paddingBottom: 32 },
  intro: { fontFamily: fonts.body, fontSize: 14, lineHeight: 21 },
  step: { gap: 8 },
  stepHead: { flexDirection: "row", alignItems: "center", gap: 10 },
  stepNum: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
  },
  stepNumText: { fontFamily: fonts.bodyHeavy, fontSize: 13 },
  stepTitle: { flex: 1, fontFamily: fonts.bodyHeavy, fontSize: 15.5 },
  stepBody: { fontFamily: fonts.body, fontSize: 13.5, lineHeight: 20 },
});
