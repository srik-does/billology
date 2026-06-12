// Bill detail / explanation view (US3). All amounts are rendered straight from
// the structured record; the LLM explanation provides only the plain-language
// description text beside each figure (Principle I — numbers come from the record).

import { ScrollView, StyleSheet, Text, View } from "react-native";

import { DiscrepancyList, type DiscrepancyFlag } from "../components/DiscrepancyList";
import { fonts, useTheme } from "../theme";

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
  const { c } = useTheme();
  const lineExpl = bill.explanation?.line_explanations ?? {};

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={styles.container}>
      <Text style={[styles.merchant, { color: c.text }]}>{bill.merchant?.value ?? "Bill"}</Text>
      {bill.bill_date?.value && <Text style={[styles.sub, { color: c.muted }]}>{bill.bill_date.value}</Text>}

      {bill.explanation?.bill_summary ? (
        <Text style={[styles.summary, { color: c.text }]}>{bill.explanation.bill_summary}</Text>
      ) : null}

      <DiscrepancyList flags={bill.discrepancies} />

      <Text style={[styles.section, { color: c.muted }]}>Items</Text>
      {(bill.line_items ?? []).map((item) => (
        <View key={item.position} style={[styles.itemRow, { borderBottomColor: c.line }]}>
          <View style={styles.itemText}>
            <Text style={[styles.itemDesc, { color: c.text }]}>{item.description?.value ?? "Item"}</Text>
            {lineExpl[String(item.position)] ? (
              <Text style={[styles.itemExpl, { color: c.muted }]}>
                {lineExpl[String(item.position)]}
              </Text>
            ) : null}
          </View>
          <Text style={[styles.itemAmount, { color: c.text }]}>{money(item.line_total)}</Text>
        </View>
      ))}
      {bill.nothing_to_verify && (
        <Text style={[styles.note, { color: c.muted }]}>No itemized breakdown — nothing to verify.</Text>
      )}

      <View style={styles.totals}>
        {bill.subtotal?.value && <Row label="Subtotal" value={money(bill.subtotal)} />}
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
  const { c } = useTheme();
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, { color: c.text }, bold && styles.bold]}>{label}</Text>
      <Text style={[styles.rowValue, { color: c.text }, bold && styles.boldValue]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 8, paddingBottom: 32 },
  merchant: { fontSize: 24, fontFamily: fonts.display },
  sub: { fontFamily: fonts.body },
  summary: { fontSize: 15, marginTop: 4, fontFamily: fonts.body, lineHeight: 22 },
  section: {
    marginTop: 16,
    fontSize: 13,
    fontFamily: fonts.bodyBold,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 7,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  itemText: { flex: 1, paddingRight: 12 },
  itemDesc: { fontSize: 15, fontFamily: fonts.body },
  itemExpl: { fontSize: 12, fontFamily: fonts.body, marginTop: 1 },
  itemAmount: { fontSize: 15, fontVariant: ["tabular-nums"], fontFamily: fonts.bodySemi },
  note: { fontStyle: "italic", marginTop: 4, fontFamily: fonts.body },
  totals: { marginTop: 16, gap: 4 },
  row: { flexDirection: "row", justifyContent: "space-between" },
  rowLabel: { fontSize: 15, fontFamily: fonts.body },
  rowValue: { fontSize: 15, fontVariant: ["tabular-nums"], fontFamily: fonts.body },
  bold: { fontFamily: fonts.bodyHeavy },
  boldValue: { fontFamily: fonts.display, fontSize: 17 },
});
