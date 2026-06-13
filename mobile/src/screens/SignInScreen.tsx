// Sign-in gate. Shown when no user is signed in (mandatory auth). A single
// "Continue with Google" action; on success the auth store updates and the
// app navigator takes over (see navigation/index.tsx).

import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { signInWithGoogle } from "../auth";
import { useT } from "../i18n";
import { fonts, radius, useTheme } from "../theme";

export function SignInScreen() {
  const t = useT();
  const { c } = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSignIn() {
    setBusy(true);
    setError(null);
    try {
      await signInWithGoogle();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={[styles.fill, { backgroundColor: c.bg }]}>
      <View style={styles.body}>
        <Text style={[styles.wordmark, { color: c.text }]}>
          Bill<Text style={{ color: c.accent }}>ology</Text>
        </Text>
        <Text style={[styles.tag, { color: c.muted }]}>{t("signInSubtitle")}</Text>

        <Pressable
          onPress={onSignIn}
          disabled={busy}
          style={({ pressed }) => [
            styles.googleBtn,
            { backgroundColor: c.card, borderColor: c.line },
            (pressed || busy) && { opacity: 0.7 },
          ]}
        >
          {busy ? (
            <ActivityIndicator color={c.accent} />
          ) : (
            <>
              <Ionicons name="logo-google" size={20} color={c.accent} />
              <Text style={[styles.googleText, { color: c.text }]}>{t("continueWithGoogle")}</Text>
            </>
          )}
        </Pressable>

        {error ? <Text style={[styles.error, { color: c.warn }]}>{error}</Text> : null}
        <Text style={[styles.fine, { color: c.muted }]}>{t("signInPrivacy")}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  body: { flex: 1, alignItems: "center", justifyContent: "center", padding: 28, gap: 14 },
  wordmark: { fontSize: 44, fontFamily: fonts.display },
  tag: { fontFamily: fonts.body, fontSize: 14.5, textAlign: "center", marginBottom: 18, lineHeight: 21 },
  googleBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: 14,
    paddingHorizontal: 22,
    minWidth: 260,
  },
  googleText: { fontFamily: fonts.bodyBold, fontSize: 15.5 },
  error: { fontFamily: fonts.bodySemi, fontSize: 13, textAlign: "center" },
  fine: { fontFamily: fonts.body, fontSize: 12, textAlign: "center", marginTop: 8, lineHeight: 17 },
});
