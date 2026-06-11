// Capture screen (US1): submit a bill as a single image, a PDF, or pasted text.
// Talks only to the backend `/bills:process` endpoint (Principle IV) and surfaces
// the "couldn't read a bill" decline (HTTP 422). On a successful candidate, it
// offers to continue to the Review screen to correct + save.

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
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";

import { ApiError, apiPostForm } from "../api/client";
import { Btn, Card } from "../components/UI";
import { useT } from "../i18n";
import type { OriginalFile, RootStackParamList } from "../navigation";
import { colors } from "../theme";

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
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [originalFile, setOriginalFile] = useState<OriginalFile | undefined>(undefined);

  async function submit(form: FormData, file?: OriginalFile) {
    setBusy(true);
    setCandidate(null);
    setOriginalFile(file);
    try {
      const result = await apiPostForm<Candidate>("/bills:process", form);
      setCandidate(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        Alert.alert("Couldn't read a bill", err.message);
      } else {
        Alert.alert("Something went wrong", String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitText() {
    if (!text.trim()) {
      Alert.alert("Paste some bill text first");
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

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.container}>
      <Text style={styles.heading}>{t("addBill")}</Text>
      <Text style={styles.sub}>{t("addBillSub")}</Text>

      <View style={styles.row}>
        <Btn title={t("pickImage")} onPress={submitImage} disabled={busy} style={styles.grow} />
        <Btn title={t("pickPdf")} onPress={submitPdf} disabled={busy} variant="secondary" style={styles.grow} />
      </View>

      <Text style={styles.label}>{t("orPaste")}</Text>
      <TextInput
        style={styles.input}
        multiline
        value={text}
        onChangeText={setText}
        placeholder={t("pastePlaceholder")}
        placeholderTextColor={colors.muted}
      />
      <Btn title={t("processText")} onPress={submitText} disabled={busy} busy={busy} />

      {busy && <ActivityIndicator style={styles.spinner} color={colors.accent} />}

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
            <Text style={styles.warn}>{t("unsupportedLayout")}</Text>
          )}
          {lowQuality && <Text style={styles.warn}>{t("lowQuality")}</Text>}
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
  container: { padding: 16, gap: 12 },
  heading: { fontSize: 24, fontWeight: "800", color: colors.text },
  sub: { color: colors.muted, fontSize: 13.5, lineHeight: 19, marginTop: -6 },
  row: { flexDirection: "row", gap: 10, marginTop: 4 },
  grow: { flex: 1 },
  label: { marginTop: 10, fontWeight: "600", color: colors.text },
  input: {
    minHeight: 120,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 10,
    padding: 10,
    textAlignVertical: "top",
    color: colors.text,
  },
  spinner: { marginTop: 12 },
  result: { marginTop: 8, gap: 6 },
  resultTitle: { fontSize: 17, fontWeight: "700", color: colors.text, marginBottom: 4 },
  resultRow: { flexDirection: "row", justifyContent: "space-between" },
  resultKey: { color: colors.muted, fontSize: 14 },
  resultVal: { color: colors.text, fontSize: 14, fontWeight: "600" },
  warn: { color: colors.warn, marginTop: 6, fontSize: 13 },
});
