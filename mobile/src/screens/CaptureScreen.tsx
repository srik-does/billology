// Capture screen (US1): submit a bill as a single image, a PDF, or pasted text.
// Talks only to the backend `/bills:process` endpoint (Principle IV) and surfaces
// the "couldn't read a bill" decline (HTTP 422). On a successful candidate, it
// offers to continue to the Review screen to correct + save.

import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
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
import type { OriginalFile, RootStackParamList } from "../navigation";

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

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Add a bill</Text>

      <View style={styles.row}>
        <Button title="Take/Pick image" onPress={submitImage} disabled={busy} />
        <Button title="Pick PDF" onPress={submitPdf} disabled={busy} />
      </View>

      <Text style={styles.label}>Or paste bill text</Text>
      <TextInput
        style={styles.input}
        multiline
        value={text}
        onChangeText={setText}
        placeholder="Paste the bill text here…"
      />
      <Button title="Process pasted text" onPress={submitText} disabled={busy} />

      {busy && <ActivityIndicator style={styles.spinner} />}

      {candidate && (
        <View style={styles.result}>
          <Text style={styles.resultLine}>Merchant: {candidate.merchant?.value ?? "—"}</Text>
          <Text style={styles.resultLine}>Type: {candidate.bill_type}</Text>
          <Text style={styles.resultLine}>Total: ₹{candidate.total_amount?.value ?? "—"}</Text>
          <Text style={styles.resultLine}>
            Line items: {candidate.line_items?.length ?? 0}
            {candidate.nothing_to_verify ? " (nothing to verify)" : ""}
          </Text>
          {candidate.layout_supported === false && (
            <Text style={styles.warn}>Unsupported layout — extracted best-effort.</Text>
          )}
          {!(Number(candidate.total_amount?.value) > 0) && (
            <Text style={styles.warn}>
              ⚠ Couldn't reliably read a total — figures may be incomplete. Try a clearer
              photo, or fix the values in Review.
            </Text>
          )}
          <View style={styles.reviewBtn}>
            <Button
              title="Review & Save →"
              onPress={() => navigation.navigate("Review", { candidate, originalFile })}
            />
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  heading: { fontSize: 22, fontWeight: "600" },
  row: { flexDirection: "row", gap: 12 },
  label: { marginTop: 8, fontWeight: "500" },
  input: {
    minHeight: 120,
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 8,
    textAlignVertical: "top",
  },
  spinner: { marginTop: 16 },
  result: { marginTop: 16, padding: 12, backgroundColor: "#f3f4f6", borderRadius: 8, gap: 4 },
  resultLine: { fontSize: 15 },
  warn: { color: "#b45309", marginTop: 4 },
  reviewBtn: { marginTop: 12 },
});
