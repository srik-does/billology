// Renders provable discrepancy flags with the conflicting figures that justify
// each one (Principle II — every flag carries its evidence). Empty list ⇒ render
// nothing, so a clean bill shows no alarms.

import { StyleSheet, Text, View } from "react-native";

export type DiscrepancyFlag = {
  kind: "sum_mismatch" | "duplicate_item" | "tax_mismatch";
  conflicting_figures: Record<string, string | number | null>;
  explanation_text: string;
  // false ⇒ a low-confidence scan fed this check; show it as "couldn't verify —
  // please check", not as a confirmed error. Absent/true ⇒ proven discrepancy.
  verified?: boolean;
};

const KIND_LABEL: Record<DiscrepancyFlag["kind"], string> = {
  sum_mismatch: "Totals don't add up",
  duplicate_item: "Possible duplicate charge",
  tax_mismatch: "Tax looks wrong",
};

export function DiscrepancyList({ flags }: { flags?: DiscrepancyFlag[] }) {
  if (!flags || flags.length === 0) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>⚠ {flags.length} thing{flags.length > 1 ? "s" : ""} to check</Text>
      {flags.map((flag, idx) => {
        const unverified = flag.verified === false;
        return (
        <View key={idx} style={[styles.card, unverified && styles.cardUnverified]}>
          <Text style={[styles.kind, unverified && styles.kindUnverified]}>
            {unverified ? "Couldn't verify — please check the scan" : KIND_LABEL[flag.kind]}
          </Text>
          <Text style={styles.explanation}>{flag.explanation_text}</Text>
          <View style={styles.figures}>
            {Object.entries(flag.conflicting_figures).map(([key, value]) => (
              <Text key={key} style={styles.figure}>
                {key.replace(/_/g, " ")}: {value ?? "—"}
              </Text>
            ))}
          </View>
        </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 12, gap: 8 },
  heading: { fontSize: 16, fontWeight: "700", color: "#b45309" },
  card: {
    borderLeftWidth: 4,
    borderLeftColor: "#f59e0b",
    backgroundColor: "#fffbeb",
    borderRadius: 6,
    padding: 10,
    gap: 4,
  },
  kind: { fontWeight: "600", color: "#92400e" },
  // Unverified (low-confidence scan): a calmer "please check" prompt in blue,
  // visually distinct from the amber confirmed-discrepancy cards.
  cardUnverified: { borderLeftColor: "#3b82f6", backgroundColor: "#eff6ff" },
  kindUnverified: { color: "#1d4ed8" },
  explanation: { fontSize: 14, color: "#1f2937" },
  figures: { marginTop: 4, gap: 2 },
  figure: { fontSize: 12, color: "#6b7280" },
});
