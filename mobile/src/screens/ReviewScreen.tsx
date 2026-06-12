// Review & save (US5 + US6 category control). Shows extracted fields with
// low-confidence marking, lets the user edit (marking edits user-provided),
// pick an editable date, and accept/change the suggested category. When the
// bill carries no date, a prompt asks the user to either read it off the bill
// (the photo is shown) or set one themselves. Saves via POST /bills.

import { useState } from "react";
import {
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
import { Ionicons } from "@expo/vector-icons";

import { apiPostForm } from "../api/client";
import { DiscrepancyList, type DiscrepancyFlag } from "../components/DiscrepancyList";
import { Btn, Chip } from "../components/UI";
import { useT } from "../i18n";
import { markBillSaved } from "../store";
import { fonts, radius, SEED_CATEGORIES, useTheme } from "../theme";

const LOW_CONFIDENCE = 0.6;

type Traced = { value?: string | null; provenance?: string; confidence?: number | null; source_ref?: unknown };
type LineItem = { position: number; description?: Traced; line_total?: Traced };
type Candidate = {
  merchant?: Traced;
  bill_date?: Traced | null;
  total_amount?: Traced;
  line_items?: LineItem[];
  discrepancies?: DiscrepancyFlag[];
  category?: { name?: string } | null;
  [k: string]: unknown;
};

function userProvided(value: string): Traced {
  return { value, provenance: "user_provided", source_ref: null };
}

function isLow(t?: Traced | null): boolean {
  return !!t && t.provenance === "extracted" && typeof t.confidence === "number" && t.confidence < LOW_CONFIDENCE;
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReviewScreen({
  candidate,
  originalFiles,
  onSaved,
}: {
  candidate: Candidate;
  originalFiles?: { uri: string; name: string; type: string }[];
  onSaved?: (billId?: string) => void;
}) {
  const t = useT();
  const { c } = useTheme();
  const [merchant, setMerchant] = useState(candidate.merchant?.value ?? "");
  const [date, setDate] = useState(candidate.bill_date?.value ?? "");
  const [category, setCategory] = useState(candidate.category?.name ?? "Other");
  const [busy, setBusy] = useState(false);

  // Missing-date prompt (#8): choose to read the date off the bill (photo
  // shown) or set one manually; either way the value is user_provided.
  const [datePrompt, setDatePrompt] = useState<"choice" | "from-bill" | "manual" | null>(
    candidate.bill_date?.value ? null : "choice"
  );
  const [promptDate, setPromptDate] = useState("");
  const billImage = originalFiles?.find((f) => f.type.startsWith("image/"));

  async function save() {
    setBusy(true);
    try {
      const payload: Candidate = { ...candidate };
      // Mark edits as user-provided (FR-004).
      if (merchant !== (candidate.merchant?.value ?? "")) {
        payload.merchant = userProvided(merchant);
      }
      if (date !== (candidate.bill_date?.value ?? "")) {
        payload.bill_date = date ? userProvided(date) : null;
      }
      payload.category = { name: category };

      const form = new FormData();
      form.append("candidate", JSON.stringify(payload));
      for (const file of originalFiles ?? []) {
        form.append("files", file as unknown as Blob);
      }
      // retries=0: saving is not idempotent — a retry after a dropped
      // connection could persist the bill twice.
      const saved = await apiPostForm<{ id?: string }>("/bills", form, 0);
      // Clear the home screen's analyzed candidate, then head back home
      // once the user dismisses the confirmation.
      markBillSaved();
      Alert.alert("Saved", "Your bill has been saved.", [
        { text: "OK", onPress: () => onSaved?.(saved.id) },
      ]);
    } catch (err) {
      Alert.alert("Couldn't save", String(err));
    } finally {
      setBusy(false);
    }
  }

  function acceptPromptDate() {
    if (promptDate.trim()) setDate(promptDate.trim());
    setDatePrompt(null);
  }

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={styles.container}>
      <Field label={t("merchant")} low={isLow(candidate.merchant)}>
        <TextInput
          style={[styles.input, { backgroundColor: c.card, borderColor: c.line, color: c.text }]}
          value={merchant}
          onChangeText={setMerchant}
        />
      </Field>

      <Field label={t("billDate")} low={isLow(candidate.bill_date)}>
        <View style={styles.dateRow}>
          <TextInput
            style={[
              styles.input,
              { flex: 1, backgroundColor: c.card, borderColor: c.line, color: c.text },
            ]}
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.muted}
          />
          <Chip label={t("dateToday")} onPress={() => setDate(todayISO())} />
        </View>
      </Field>

      <Text style={[styles.label, { color: c.text }]}>{t("category")}</Text>
      <View style={styles.chips}>
        {SEED_CATEGORIES.map((name) => (
          <Chip key={name} label={name} active={category === name} onPress={() => setCategory(name)} />
        ))}
      </View>

      <DiscrepancyList flags={candidate.discrepancies} />

      <Text style={[styles.label, { color: c.text }]}>{t("items")}</Text>
      {(candidate.line_items ?? []).map((item) => (
        <View key={item.position} style={[styles.itemRow, { borderBottomColor: c.line }]}>
          <Text style={[styles.itemDesc, { color: c.text }]}>
            {item.description?.value ?? "Item"}
            {isLow(item.description) || isLow(item.line_total) ? (
              <Text style={[styles.flag, { color: c.warn }]}> ⚠ check</Text>
            ) : null}
          </Text>
          <Text style={[styles.itemAmount, { color: c.text }]}>
            ₹{item.line_total?.value ?? "—"}
          </Text>
        </View>
      ))}

      <View style={styles.totalRow}>
        <Text style={[styles.totalLabel, { color: c.text }]}>{t("total")}</Text>
        <Text style={[styles.totalValue, { color: c.text }]}>
          ₹{candidate.total_amount?.value ?? "—"}
        </Text>
      </View>

      <View style={styles.saveBtn}>
        <Btn title={t("saveBill")} onPress={save} busy={busy} />
      </View>

      {/* --- Missing-date prompt -------------------------------------------- */}
      <Modal visible={datePrompt !== null} transparent animationType="fade">
        <View style={styles.backdrop}>
          <View style={[styles.sheet, { backgroundColor: c.card, borderColor: c.line }]}>
            <View style={[styles.sheetIcon, { backgroundColor: c.accentSoft }]}>
              <Ionicons name="calendar-outline" size={22} color={c.accent} />
            </View>
            <Text style={[styles.sheetTitle, { color: c.text }]}>{t("dateNeededTitle")}</Text>

            {datePrompt === "choice" && (
              <>
                <Text style={[styles.sheetBody, { color: c.muted }]}>{t("dateNeededBody")}</Text>
                {billImage && (
                  <Pressable
                    style={[styles.option, { borderColor: c.line, backgroundColor: c.well }]}
                    onPress={() => {
                      setPromptDate("");
                      setDatePrompt("from-bill");
                    }}
                  >
                    <Ionicons name="receipt-outline" size={19} color={c.accent} />
                    <Text style={[styles.optionText, { color: c.text }]}>{t("dateFromBill")}</Text>
                    <Ionicons name="chevron-forward" size={17} color={c.muted} />
                  </Pressable>
                )}
                <Pressable
                  style={[styles.option, { borderColor: c.line, backgroundColor: c.well }]}
                  onPress={() => {
                    setPromptDate(todayISO());
                    setDatePrompt("manual");
                  }}
                >
                  <Ionicons name="create-outline" size={19} color={c.accent} />
                  <Text style={[styles.optionText, { color: c.text }]}>{t("dateSetManual")}</Text>
                  <Ionicons name="chevron-forward" size={17} color={c.muted} />
                </Pressable>
                <Pressable onPress={() => setDatePrompt(null)} hitSlop={8}>
                  <Text style={[styles.skip, { color: c.muted }]}>{t("dateSkip")}</Text>
                </Pressable>
              </>
            )}

            {datePrompt === "from-bill" && (
              <>
                <Text style={[styles.sheetBody, { color: c.muted }]}>{t("dateFromBillHint")}</Text>
                {billImage && (
                  <Image
                    source={{ uri: billImage.uri }}
                    style={[styles.billPreview, { borderColor: c.line }]}
                    resizeMode="contain"
                  />
                )}
                <TextInput
                  style={[styles.input, { backgroundColor: c.well, borderColor: c.line, color: c.text }]}
                  value={promptDate}
                  onChangeText={setPromptDate}
                  placeholder="YYYY-MM-DD"
                  placeholderTextColor={c.muted}
                  autoFocus
                />
                <Btn title={t("dateDone")} onPress={acceptPromptDate} disabled={!promptDate.trim()} />
                <Pressable onPress={() => setDatePrompt("choice")} hitSlop={8}>
                  <Text style={[styles.skip, { color: c.muted }]}>‹ {t("dateSetManual")}</Text>
                </Pressable>
              </>
            )}

            {datePrompt === "manual" && (
              <>
                <View style={styles.dateRow}>
                  <TextInput
                    style={[
                      styles.input,
                      { flex: 1, backgroundColor: c.well, borderColor: c.line, color: c.text },
                    ]}
                    value={promptDate}
                    onChangeText={setPromptDate}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={c.muted}
                    autoFocus
                  />
                  <Chip label={t("dateToday")} onPress={() => setPromptDate(todayISO())} />
                </View>
                <Btn title={t("dateDone")} onPress={acceptPromptDate} disabled={!promptDate.trim()} />
                <Pressable onPress={() => setDatePrompt(null)} hitSlop={8}>
                  <Text style={[styles.skip, { color: c.muted }]}>{t("dateSkip")}</Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function Field({ label, low, children }: { label: string; low?: boolean; children: React.ReactNode }) {
  const { c } = useTheme();
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: c.text }]}>
        {label}
        {low ? <Text style={[styles.flag, { color: c.warn }]}> ⚠ check</Text> : null}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 10, paddingBottom: 32 },
  field: { gap: 4 },
  label: { fontFamily: fonts.bodyBold, marginTop: 6, fontSize: 14 },
  input: { borderWidth: 1, borderRadius: radius.md, padding: 10, fontFamily: fonts.body },
  dateRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  flag: { fontFamily: fonts.bodySemi, fontSize: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  itemDesc: { flex: 1, paddingRight: 12, fontFamily: fonts.body, fontSize: 14.5 },
  itemAmount: { fontVariant: ["tabular-nums"], fontFamily: fonts.bodySemi, fontSize: 14.5 },
  totalRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 12 },
  totalLabel: { fontFamily: fonts.bodyHeavy, fontSize: 16 },
  totalValue: { fontFamily: fonts.display, fontSize: 18, fontVariant: ["tabular-nums"] },
  saveBtn: { marginTop: 20 },

  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,12,8,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: 22,
  },
  sheet: {
    width: "100%",
    borderRadius: radius.xl,
    borderWidth: 1,
    padding: 20,
    gap: 12,
  },
  sheetIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  sheetTitle: { fontFamily: fonts.display, fontSize: 20 },
  sheetBody: { fontFamily: fonts.body, fontSize: 13.5, lineHeight: 19 },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  optionText: { flex: 1, fontFamily: fonts.bodyBold, fontSize: 14.5 },
  skip: { textAlign: "center", fontFamily: fonts.bodySemi, fontSize: 13, paddingVertical: 4 },
  billPreview: { width: "100%", height: 260, borderRadius: radius.md, borderWidth: 1 },
});
