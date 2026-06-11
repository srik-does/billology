// Capture screen (US1): submit a bill as a single image, a PDF, or pasted text.
// Talks only to the backend `/bills:process` endpoint (Principle IV) and surfaces
// the "couldn't read a bill" decline (HTTP 422) as an inline banner. On a
// successful candidate, it offers to continue to the Review screen.

import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { LinearGradient } from "expo-linear-gradient";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";

import { ApiError, apiPostForm } from "../api/client";
import { ActionTile, Banner, Btn, Card, SectionTitle } from "../components/UI";
import { useT } from "../i18n";
import type { OriginalFile, RootStackParamList } from "../navigation";
import { colors, heroGradient, radius } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Capture">;

type Candidate = {
  merchant?: { value?: string };
  bill_type?: string;
  total_amount?: { value?: string };
  line_items?: unknown[];
  nothing_to_verify?: boolean;
  layout_supported?: boolean;
};

export function CaptureScreen() {
  const navigation = useNavigation<Nav>();
  const t = useT();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [originalFile, setOriginalFile] = useState<OriginalFile | undefined>(undefined);

  async function submit(form: FormData, file?: OriginalFile) {
    setBusy(true);
    setNotice(null);
    setCandidate(null);
    setOriginalFile(file);
    try {
      const result = await apiPostForm<Candidate>("/bills:process", form);
      setCandidate(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        // Friendly decline (e.g. "not a bill", page cap) — inline, not a popup.
        setNotice(err.message);
      } else {
        Alert.alert("Something went wrong", String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitText() {
    if (!text.trim()) {
      setNotice(t("pastePlaceholder"));
      return;
    }
    const form = new FormData();
    form.append("text", text);
    await submit(form, undefined);
  }

  async function submitImage() {
    const picked = await ImagePicker.launchImageLibraryAsync({ quality: 1 });
    if (picked.canceled || !picked.assets?.length) return;
    const asset = picked.assets[0];
    const file: OriginalFile = {
      uri: asset.uri,
      name: asset.fileName ?? "bill.jpg",
      type: asset.mimeType ?? "image/jpeg",
    };
    const form = new FormData();
    form.append("files", file as unknown as Blob);
    await submit(form, file);
  }

  async function submitPdf() {
    const picked = await DocumentPicker.getDocumentAsync({ type: "application/pdf" });
    if (picked.canceled || !picked.assets?.length) return;
    const asset = picked.assets[0];
    const file: OriginalFile = { uri: asset.uri, name: asset.name ?? "bill.pdf", type: "application/pdf" };
    const form = new FormData();
    form.append("files", file as unknown as Blob);
    await submit(form, file);
  }

  const lowQuality = candidate && !(Number(candidate.total_amount?.value) > 0);
  // The keys carry a leading pictograph for the old buttons; tiles bring
  // their own icons, so strip it.
  const tileLabel = (s: string) => s.replace(/^📷 |^📄 /, "");

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.container}>
      <LinearGradient
        colors={[...heroGradient]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.hero}
      >
        <Text style={styles.heroEmoji}>🧾</Text>
        <Text style={styles.heroTitle}>{t("addBill")}</Text>
        <Text style={styles.heroSub}>{t("addBillSub")}</Text>
      </LinearGradient>

      <View style={styles.row}>
        <ActionTile
          icon="image-outline"
          label={tileLabel(t("pickImage"))}
          onPress={submitImage}
          disabled={busy}
        />
        <ActionTile
          icon="document-text-outline"
          label={tileLabel(t("pickPdf"))}
          onPress={submitPdf}
          disabled={busy}
        />
      </View>

      <SectionTitle>{t("orPaste")}</SectionTitle>
      <Card style={styles.pasteCard}>
        <TextInput
          style={styles.input}
          multiline
          value={text}
          onChangeText={setText}
          placeholder={t("pastePlaceholder")}
          placeholderTextColor={colors.muted}
        />
        <Btn title={t("processText")} onPress={submitText} disabled={busy} busy={busy} />
      </Card>

      {busy && <ActivityIndicator style={styles.spinner} color={colors.accent} />}
      {notice && <Banner kind="warn" text={notice} />}

      {candidate && (
        <Card style={styles.result}>
          <Text style={styles.resultTitle}>{candidate.merchant?.value ?? "Bill"}</Text>
          <View style={styles.resultRow}>
            <Text style={styles.resultKey}>{t("type")}</Text>
            <Text style={styles.resultVal}>{candidate.bill_type}</Text>
          </View>
          <View style={styles.resultRow}>
            <Text style={styles.resultKey}>{t("total")}</Text>
            <Text style={styles.resultVal}>₹{candidate.total_amount?.value ?? "—"}</Text>
          </View>
          <View style={styles.resultRow}>
            <Text style={styles.resultKey}>{t("lineItems")}</Text>
            <Text style={styles.resultVal}>
              {candidate.line_items?.length ?? 0}
              {candidate.nothing_to_verify ? t("nothingToVerify") : ""}
            </Text>
          </View>
          {candidate.layout_supported === false && (
            <Banner kind="warn" text={t("unsupportedLayout")} />
          )}
          {lowQuality && <Banner kind="warn" text={t("lowQuality")} />}
          <Btn
            title={t("reviewSave")}
            onPress={() => navigation.navigate("Review", { candidate, originalFile })}
            style={{ marginTop: 12 }}
          />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { backgroundColor: colors.bg },
  container: { padding: 16, gap: 14, paddingBottom: 28 },
  hero: { borderRadius: radius.xl, padding: 20, gap: 6 },
  heroEmoji: { fontSize: 34 },
  heroTitle: { fontSize: 24, fontWeight: "800", color: "#ffffff" },
  heroSub: { color: "rgba(255,255,255,0.88)", fontSize: 13.5, lineHeight: 19 },
  row: { flexDirection: "row", gap: 12 },
  pasteCard: { gap: 12 },
  input: {
    minHeight: 110,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: 12,
    textAlignVertical: "top",
    color: colors.text,
  },
  spinner: { marginTop: 4 },
  result: { gap: 8 },
  resultTitle: { fontSize: 17, fontWeight: "700", color: colors.text, marginBottom: 2 },
  resultRow: { flexDirection: "row", justifyContent: "space-between" },
  resultKey: { color: colors.muted, fontSize: 14 },
  resultVal: { color: colors.text, fontSize: 14, fontWeight: "600" },
});
