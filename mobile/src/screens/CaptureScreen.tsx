// Capture screen (US1): submit a bill via the in-app camera (multi-page),
// gallery image(s), a PDF, or pasted text. Talks only to the backend
// `/bills:process` endpoint (Principle IV) and surfaces the "couldn't read a
// bill" decline (HTTP 422) as an inline banner. On a successful candidate, it
// offers to continue to the Review screen.
//
// The paste box stays hidden until its button is pressed — the landing view
// shows only the action buttons. The camera sheet mirrors a UPI-style layout:
// full-screen viewfinder, big round shutter at the bottom, captured-page
// thumbnails beside it, and an upload button once at least one page is shot.

import { useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { LinearGradient } from "expo-linear-gradient";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { Ionicons } from "@expo/vector-icons";

import { ApiError, apiPostForm } from "../api/client";
import { ActionTile, Banner, Btn, Card, SectionTitle } from "../components/UI";
import { useT } from "../i18n";
import type { OriginalFile, RootStackParamList } from "../navigation";
import { fonts, radius, useTheme, type Palette } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Capture">;

type Candidate = {
  merchant?: { value?: string };
  bill_type?: string;
  bill_date?: { value?: string } | null;
  total_amount?: { value?: string };
  line_items?: unknown[];
  nothing_to_verify?: boolean;
  layout_supported?: boolean;
};

const MAX_PHOTOS = 5; // matches the backend's vision page budget

/** Decorative mini-receipt graphic for the hero — drawn, not an emoji. */
function ReceiptArt({ c }: { c: Palette }) {
  return (
    <View style={art.wrap}>
      <View style={art.paper}>
        <View style={[art.line, { width: "62%" }]} />
        <View style={[art.line, { width: "44%" }]} />
        <View style={art.gap} />
        <View style={art.row}>
          <View style={[art.line, { width: "38%" }]} />
          <View style={[art.line, { width: "18%" }]} />
        </View>
        <View style={art.row}>
          <View style={[art.line, { width: "46%" }]} />
          <View style={[art.line, { width: "14%" }]} />
        </View>
        <View style={art.dashes}>
          {Array.from({ length: 7 }).map((_, i) => (
            <View key={i} style={art.dash} />
          ))}
        </View>
        <View style={art.row}>
          <View style={[art.lineBold, { width: "30%" }]} />
          <View style={[art.lineBold, { width: "22%", backgroundColor: "#0F766E" }]} />
        </View>
      </View>
      <View style={[art.badge, { backgroundColor: c.gold }]}>
        <Ionicons name="checkmark" size={14} color="#FFFFFF" />
      </View>
    </View>
  );
}

const art = StyleSheet.create({
  wrap: { width: 84, height: 96 },
  paper: {
    flex: 1,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 10,
    borderBottomLeftRadius: 2,
    borderBottomRightRadius: 2,
    padding: 10,
    gap: 6,
    transform: [{ rotate: "-4deg" }],
  },
  line: { height: 5, borderRadius: 3, backgroundColor: "#D9D2C3" },
  lineBold: { height: 7, borderRadius: 3, backgroundColor: "#8F867A" },
  gap: { height: 2 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  dashes: { flexDirection: "row", justifyContent: "space-between", marginVertical: 2 },
  dash: { width: 6, height: 2, borderRadius: 1, backgroundColor: "#D9D2C3" },
  badge: {
    position: "absolute",
    right: -6,
    bottom: -4,
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
});

export function CaptureScreen() {
  const navigation = useNavigation<Nav>();
  const t = useT();
  const { c } = useTheme();
  const [text, setText] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [originalFiles, setOriginalFiles] = useState<OriginalFile[]>([]);

  // Camera sheet state.
  const [cameraOpen, setCameraOpen] = useState(false);
  const [shots, setShots] = useState<OriginalFile[]>([]);
  const [snapping, setSnapping] = useState(false);
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();

  async function submit(form: FormData, files: OriginalFile[]) {
    setBusy(true);
    setNotice(null);
    setCandidate(null);
    setOriginalFiles(files);
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
    await submit(form, []);
  }

  async function submitFiles(files: OriginalFile[]) {
    const form = new FormData();
    for (const file of files) form.append("files", file as unknown as Blob);
    await submit(form, files);
  }

  async function pickFromGallery() {
    const picked = await ImagePicker.launchImageLibraryAsync({
      quality: 1,
      allowsMultipleSelection: true,
      selectionLimit: MAX_PHOTOS,
    });
    if (picked.canceled || !picked.assets?.length) return;
    await submitFiles(
      picked.assets.map((asset, i) => ({
        uri: asset.uri,
        name: asset.fileName ?? `bill-${i + 1}.jpg`,
        type: asset.mimeType ?? "image/jpeg",
      }))
    );
  }

  async function pickPdf() {
    const picked = await DocumentPicker.getDocumentAsync({ type: "application/pdf" });
    if (picked.canceled || !picked.assets?.length) return;
    const asset = picked.assets[0];
    await submitFiles([
      { uri: asset.uri, name: asset.name ?? "bill.pdf", type: "application/pdf" },
    ]);
  }

  // --- Camera sheet ---------------------------------------------------------

  async function openCamera() {
    if (!permission?.granted) {
      const res = await requestPermission();
      if (!res.granted) {
        setNotice("Camera permission is needed to photograph bills.");
        return;
      }
    }
    setShots([]);
    setCameraOpen(true);
  }

  async function snap() {
    if (snapping || shots.length >= MAX_PHOTOS) return;
    setSnapping(true);
    try {
      const photo = await cameraRef.current?.takePictureAsync({ quality: 0.9 });
      if (photo?.uri) {
        setShots((s) => [
          ...s,
          { uri: photo.uri, name: `bill-page-${s.length + 1}.jpg`, type: "image/jpeg" },
        ]);
      }
    } catch (e) {
      Alert.alert("Camera error", String(e));
    } finally {
      setSnapping(false);
    }
  }

  async function useShots() {
    setCameraOpen(false);
    if (shots.length) await submitFiles(shots);
  }

  const lowQuality = candidate && !(Number(candidate.total_amount?.value) > 0);
  // Older keys carry a leading pictograph; tiles bring their own icons.
  const tileLabel = (s: string) => s.replace(/^📷 |^📄 /, "");
  const cameraFull = shots.length >= MAX_PHOTOS;

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={styles.container}>
      <LinearGradient
        colors={[...c.hero]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.hero}
      >
        <View style={styles.heroRow}>
          <View style={styles.heroText}>
            <Text style={styles.heroTitle}>{t("addBill")}</Text>
            <Text style={styles.heroSub}>{t("addBillSub")}</Text>
          </View>
          <ReceiptArt c={c} />
        </View>
      </LinearGradient>

      <View style={styles.row}>
        <ActionTile icon="camera" label={t("takePhoto")} onPress={openCamera} disabled={busy} />
        <ActionTile
          icon="image-outline"
          label={tileLabel(t("pickImage"))}
          onPress={pickFromGallery}
          disabled={busy}
        />
      </View>
      <View style={styles.row}>
        <ActionTile
          icon="document-text-outline"
          label={tileLabel(t("pickPdf"))}
          onPress={pickPdf}
          disabled={busy}
        />
        <ActionTile
          icon="create-outline"
          label={t("pasteTextBtn")}
          onPress={() => setShowPaste((v) => !v)}
          disabled={busy}
          active={showPaste}
        />
      </View>

      {showPaste && (
        <>
          <SectionTitle>{t("orPaste")}</SectionTitle>
          <Card style={styles.pasteCard}>
            <TextInput
              style={[
                styles.input,
                { backgroundColor: c.well, borderColor: c.line, color: c.text },
              ]}
              multiline
              autoFocus
              value={text}
              onChangeText={setText}
              placeholder={t("pastePlaceholder")}
              placeholderTextColor={c.muted}
            />
            <Btn title={t("processText")} onPress={submitText} disabled={busy} busy={busy} />
          </Card>
        </>
      )}

      {busy && <ActivityIndicator style={styles.spinner} color={c.accent} />}
      {notice && <Banner kind="warn" text={notice} />}

      {candidate && (
        <Card style={styles.result}>
          <Text style={[styles.resultTitle, { color: c.text }]}>
            {candidate.merchant?.value ?? "Bill"}
          </Text>
          <View style={styles.resultRow}>
            <Text style={[styles.resultKey, { color: c.muted }]}>{t("type")}</Text>
            <Text style={[styles.resultVal, { color: c.text }]}>{candidate.bill_type}</Text>
          </View>
          <View style={styles.resultRow}>
            <Text style={[styles.resultKey, { color: c.muted }]}>{t("total")}</Text>
            <Text style={[styles.resultVal, { color: c.text }]}>
              ₹{candidate.total_amount?.value ?? "—"}
            </Text>
          </View>
          <View style={styles.resultRow}>
            <Text style={[styles.resultKey, { color: c.muted }]}>{t("lineItems")}</Text>
            <Text style={[styles.resultVal, { color: c.text }]}>
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
            onPress={() => navigation.navigate("Review", { candidate, originalFiles })}
            style={{ marginTop: 12 }}
          />
        </Card>
      )}

      {/* --- In-app camera: UPI-style bottom shutter, multi-page capture --- */}
      <Modal visible={cameraOpen} animationType="slide" onRequestClose={() => setCameraOpen(false)}>
        <View style={styles.camWrap}>
          <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />

          <View style={styles.camTop}>
            <Pressable onPress={() => setCameraOpen(false)} hitSlop={12} style={styles.camClose}>
              <Ionicons name="close" size={24} color="#FFFFFF" />
            </Pressable>
            <Text style={styles.camHint}>
              {cameraFull ? t("cameraMax") : t("cameraHint")}
            </Text>
          </View>

          <View style={styles.camBottom}>
            <View style={styles.camThumbs}>
              {shots.map((s) => (
                <Image key={s.uri} source={{ uri: s.uri }} style={styles.camThumb} />
              ))}
            </View>
            <View style={styles.camControls}>
              <View style={styles.camSide}>
                {shots.length > 0 && (
                  <Pressable
                    onPress={() => setShots((s) => s.slice(0, -1))}
                    style={styles.camRetake}
                    hitSlop={8}
                  >
                    <Ionicons name="arrow-undo-outline" size={20} color="#FFFFFF" />
                  </Pressable>
                )}
              </View>
              <Pressable
                onPress={snap}
                disabled={snapping || cameraFull}
                style={({ pressed }) => [
                  styles.shutter,
                  (snapping || cameraFull) && { opacity: 0.5 },
                  pressed && { transform: [{ scale: 0.94 }] },
                ]}
                accessibilityLabel={t("cameraShot")}
              >
                <View style={styles.shutterInner} />
              </Pressable>
              <View style={styles.camSide}>
                {shots.length > 0 && (
                  <Pressable onPress={useShots} style={[styles.camDone, { backgroundColor: c.gold }]}>
                    <Ionicons name="checkmark" size={18} color="#FFFFFF" />
                    <Text style={styles.camDoneText}>
                      {t("cameraDone").replace("{n}", String(shots.length))}
                    </Text>
                  </Pressable>
                )}
              </View>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 14, paddingBottom: 28 },
  hero: { borderRadius: radius.xl, padding: 20 },
  heroRow: { flexDirection: "row", alignItems: "center", gap: 16 },
  heroText: { flex: 1, gap: 6 },
  heroTitle: { fontSize: 26, fontFamily: fonts.display, color: "#FFFFFF" },
  heroSub: {
    color: "rgba(255,255,255,0.88)",
    fontSize: 13.5,
    lineHeight: 19,
    fontFamily: fonts.body,
  },
  row: { flexDirection: "row", gap: 12 },
  pasteCard: { gap: 12 },
  input: {
    minHeight: 110,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 12,
    textAlignVertical: "top",
    fontFamily: fonts.body,
  },
  spinner: { marginTop: 4 },
  result: { gap: 8 },
  resultTitle: { fontSize: 18, fontFamily: fonts.display, marginBottom: 2 },
  resultRow: { flexDirection: "row", justifyContent: "space-between" },
  resultKey: { fontSize: 14, fontFamily: fonts.body },
  resultVal: { fontSize: 14, fontFamily: fonts.bodyBold, fontVariant: ["tabular-nums"] },

  // Camera sheet
  camWrap: { flex: 1, backgroundColor: "#000000" },
  camTop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    paddingTop: 54,
    paddingHorizontal: 18,
    paddingBottom: 14,
    backgroundColor: "rgba(0,0,0,0.45)",
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  camClose: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  camHint: { flex: 1, color: "#FFFFFF", fontSize: 13, fontFamily: fonts.bodySemi, lineHeight: 18 },
  camBottom: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    paddingBottom: 34,
    paddingTop: 12,
    backgroundColor: "rgba(0,0,0,0.55)",
    gap: 10,
  },
  camThumbs: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 18,
    minHeight: 48,
    alignItems: "center",
  },
  camThumb: {
    width: 44,
    height: 58,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.7)",
  },
  camControls: { flexDirection: "row", alignItems: "center", paddingHorizontal: 18 },
  camSide: { flex: 1, alignItems: "center" },
  shutter: {
    width: 76,
    height: 76,
    borderRadius: 38,
    borderWidth: 5,
    borderColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  shutterInner: { width: 58, height: 58, borderRadius: 29, backgroundColor: "#FFFFFF" },
  camRetake: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  camDone: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  camDoneText: { color: "#FFFFFF", fontFamily: fonts.bodyBold, fontSize: 13 },
});
