// Review & save (US5 + US6 category control). Shows extracted fields with
// low-confidence marking, lets the user edit (marking edits user-provided), pick
// an editable date, and accept/change the suggested category (seeded list only —
// creating new categories is out of demo scope). Saves via POST /bills.

import { useState } from "react";
import {
  Alert,
  Button,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { apiPostForm } from "../api/client";
import { DiscrepancyList, type DiscrepancyFlag } from "../components/DiscrepancyList";
import { Btn } from "../components/UI";

// Mirrors backend SEED_CATEGORIES (migration 002). Kept client-side because the
// demo spine has no GET /categories endpoint.
const SEED_CATEGORIES = [
  "Telecom/Recharge",
  "Groceries",
  "Utilities",
  "Food & Dining",
  "Shopping",
  "Other",
];

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

export function ReviewScreen({
  candidate,
  originalFile,
  onSaved,
}: {
  candidate: Candidate;
  originalFile?: { uri: string; name: string; type: string };
  onSaved?: (billId?: string) => void;
}) {
  const [merchant, setMerchant] = useState(candidate.merchant?.value ?? "");
  const [date, setDate] = useState(candidate.bill_date?.value ?? "");
  const [category, setCategory] = useState(candidate.category?.name ?? "Other");
  const [busy, setBusy] = useState(false);

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
      if (originalFile) {
        form.append("files", originalFile as unknown as Blob);
      }
      const saved = await apiPostForm<{ id?: string }>("/bills", form);
      Alert.alert("Saved", "Your bill has been saved.");
      onSaved?.(saved.id);
    } catch (err) {
      Alert.alert("Couldn't save", String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Review & save</Text>

      <Field label="Merchant" low={isLow(candidate.merchant)}>
        <TextInput style={styles.input} value={merchant} onChangeText={setMerchant} />
      </Field>

      <Field label="Bill date" low={isLow(candidate.bill_date)}>
        <TextInput
          style={styles.input}
          value={date}
          onChangeText={setDate}
          placeholder="YYYY-MM-DD (optional)"
        />
      </Field>

      <Text style={styles.label}>Category</Text>
      <View style={styles.chips}>
        {SEED_CATEGORIES.map((name) => (
          <Pressable
            key={name}
            onPress={() => setCategory(name)}
            style={[styles.chip, category === name && styles.chipActive]}
          >
            <Text style={[styles.chipText, category === name && styles.chipTextActive]}>{name}</Text>
          </Pressable>
        ))}
      </View>

      <DiscrepancyList flags={candidate.discrepancies} />

      <Text style={styles.label}>Items</Text>
      {(candidate.line_items ?? []).map((item) => (
        <View key={item.position} style={styles.itemRow}>
          <Text style={styles.itemDesc}>
            {item.description?.value ?? "Item"}
            {isLow(item.description) || isLow(item.line_total) ? (
              <Text style={styles.flag}> ⚠ check</Text>
            ) : null}
          </Text>
          <Text style={styles.itemAmount}>₹{item.line_total?.value ?? "—"}</Text>
        </View>
      ))}

      <View style={styles.totalRow}>
        <Text style={styles.totalLabel}>Total</Text>
        <Text style={styles.totalValue}>₹{candidate.total_amount?.value ?? "—"}</Text>
      </View>

      <View style={styles.saveBtn}>
        <Btn title="Save bill" onPress={save} busy={busy} />
      </View>
    </ScrollView>
  );
}

function Field({ label, low, children }: { label: string; low?: boolean; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>
        {label}
        {low ? <Text style={styles.flag}> ⚠ low confidence</Text> : null}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 10 },
  heading: { fontSize: 22, fontWeight: "700" },
  field: { gap: 4 },
  label: { fontWeight: "600", marginTop: 6 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 8 },
  flag: { color: "#b45309", fontWeight: "500", fontSize: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  chipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  chipText: { color: "#374151" },
  chipTextActive: { color: "#fff" },
  itemRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#e5e7eb" },
  itemDesc: { flex: 1, paddingRight: 12 },
  itemAmount: { fontVariant: ["tabular-nums"] },
  totalRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 12 },
  totalLabel: { fontWeight: "700", fontSize: 16 },
  totalValue: { fontWeight: "700", fontSize: 16, fontVariant: ["tabular-nums"] },
  saveBtn: { marginTop: 20 },
});
