// Bill detail / explanation view (US3). All amounts are rendered straight from
// the structured record; the LLM explanation provides only the plain-language
// description text beside each figure (Principle I — numbers come from the record).

import { ScrollView, StyleSheet, Text, View } from "react-native";

import { DiscrepancyList, type DiscrepancyFlag } from "../components/DiscrepancyList";

type Traced = { value?: string | null };
type LineItem = {
  position: number;
  description?: Traced;
  line_total?: Traced;
};
export type BillCandidate = {
  merchant?: Traced;
  bill_type?: string;
  bill_date?: Traced | null;
  subtotal?: Traced | null;
  tax_rate?: Traced | null;
  tax_amount?: Traced | null;
  total_amount?: Traced;
  line_items?: LineItem[];
  discrepancies?: DiscrepancyFlag[];
  explanation?: {
    bill_summary?: string;
    line_explanations?: Record<string, string>;
  } | null;
  nothing_to_verify?: boolean;
};

function money(t?: Traced | null): string {
  return t?.value != null ? `₹${t.value}` : "—";
}

export function BillDetailScreen({ bill }: { bill: BillCandidate }) {
  const lineExpl = bill.explanation?.line_explanations ?? {};

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.merchant}>{bill.merchant?.value ?? "Bill"}</Text>
      {bill.bill_date?.value && <Text style={styles.sub}>{bill.bill_date.value}</Text>}

      {bill.explanation?.bill_summary ? (
        <Text style={styles.summary}>{bill.explanation.bill_summary}</Text>
      ) : null}

      <DiscrepancyList flags={bill.discrepancies} />

      <Text style={styles.section}>Items</Text>
      {(bill.line_items ?? []).map((item) => (
        <View key={item.position} style={styles.itemRow}>
          <View style={styles.itemText}>
            <Text style={styles.itemDesc}>{item.description?.value ?? "Item"}</Text>
            {lineExpl[String(item.position)] ? (
              <Text style={styles.itemExpl}>{lineExpl[String(item.position)]}</Text>
            ) : null}
          </View>
          <Text style={styles.itemAmount}>{money(item.line_total)}</Text>
        </View>
      ))}
      {bill.nothing_to_verify && (
        <Text style={styles.note}>No itemized breakdown — nothing to verify.</Text>
      )}

      <View style={styles.totals}>
        {bill.subtotal?.value && (
          <Row label="Subtotal" value={money(bill.subtotal)} />
        )}
        {bill.tax_amount?.value && (
          <Row
            label={`Tax${bill.tax_rate?.value ? ` (${bill.tax_rate.value}%)` : ""}`}
            value={money(bill.tax_amount)}
          />
        )}
        <Row label="Total" value={money(bill.total_amount)} bold />
      </View>
    </ScrollView>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, bold && styles.bold]}>{label}</Text>
      <Text style={[styles.rowValue, bold && styles.bold]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 8 },
  merchant: { fontSize: 22, fontWeight: "700" },
  sub: { color: "#6b7280" },
  summary: { fontSize: 15, color: "#1f2937", marginTop: 4 },
  section: { marginTop: 16, fontSize: 13, fontWeight: "700", color: "#6b7280", textTransform: "uppercase" },
  itemRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#e5e7eb" },
  itemText: { flex: 1, paddingRight: 12 },
  itemDesc: { fontSize: 15 },
  itemExpl: { fontSize: 12, color: "#6b7280" },
  itemAmount: { fontSize: 15, fontVariant: ["tabular-nums"] },
  note: { color: "#6b7280", fontStyle: "italic", marginTop: 4 },
  totals: { marginTop: 16, gap: 4 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  rowLabel: { fontSize: 15, color: "#374151" },
  rowValue: { fontSize: 15, fontVariant: ["tabular-nums"] },
  bold: { fontWeight: "700" },
});
