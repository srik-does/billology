// Spending dashboard (US8). Two views over saved records only: category
// breakdown (donut) and monthly trend (bar). Figures come from the backend's
// SQL-style aggregates — no client-side estimation.

import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { BarChart, PieChart } from "react-native-gifted-charts";

import { apiGet } from "../api/client";

type CategoryRow = { category: string; total: string };
type MonthRow = { month: string; total: string };

const PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#db2777", "#7c3aed", "#0891b2", "#9ca3af"];

export function DashboardScreen() {
  const [byCategory, setByCategory] = useState<CategoryRow[] | null>(null);
  const [monthly, setMonthly] = useState<MonthRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [cats, months] = await Promise.all([
          apiGet<CategoryRow[]>("/dashboard/by-category"),
          apiGet<MonthRow[]>("/dashboard/monthly"),
        ]);
        setByCategory(cats);
        setMonthly(months);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  if (error) return <Centered><Text style={styles.err}>{error}</Text></Centered>;
  if (!byCategory || !monthly) return <Centered><ActivityIndicator /></Centered>;

  const hasData = byCategory.length > 0 || monthly.length > 0;
  if (!hasData) {
    return <Centered><Text style={styles.empty}>No saved bills yet. Add a bill to see your spending.</Text></Centered>;
  }

  const pieData = byCategory.map((c, i) => ({
    value: Number(c.total),
    color: PALETTE[i % PALETTE.length],
    text: c.category,
  }));
  const total = byCategory.reduce((s, c) => s + Number(c.total), 0);

  const barData = monthly.map((m) => ({
    value: Number(m.total),
    label: m.month.slice(5), // MM
  }));

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Spending</Text>

      <Text style={styles.section}>By category</Text>
      <View style={styles.center}>
        <PieChart
          data={pieData}
          donut
          radius={110}
          innerRadius={70}
          centerLabelComponent={() => (
            <View style={styles.center}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>₹{total.toFixed(2)}</Text>
            </View>
          )}
        />
      </View>
      <View style={styles.legend}>
        {byCategory.map((c, i) => (
          <View key={c.category} style={styles.legendRow}>
            <View style={[styles.swatch, { backgroundColor: PALETTE[i % PALETTE.length] }]} />
            <Text style={styles.legendText}>{c.category}</Text>
            <Text style={styles.legendValue}>₹{Number(c.total).toFixed(2)}</Text>
          </View>
        ))}
      </View>

      <Text style={styles.section}>Monthly trend</Text>
      <BarChart
        data={barData}
        frontColor="#2563eb"
        barWidth={28}
        spacing={18}
        yAxisThickness={0}
        xAxisThickness={0}
        noOfSections={4}
      />
    </ScrollView>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <View style={styles.centeredFull}>{children}</View>;
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 10 },
  centeredFull: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  center: { alignItems: "center", justifyContent: "center" },
  title: { fontSize: 22, fontWeight: "700" },
  section: { marginTop: 18, fontSize: 13, fontWeight: "700", color: "#6b7280", textTransform: "uppercase" },
  totalLabel: { color: "#6b7280", fontSize: 12 },
  totalValue: { fontWeight: "700", fontSize: 16 },
  legend: { marginTop: 12, gap: 6 },
  legendRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  legendText: { flex: 1, fontSize: 14 },
  legendValue: { fontSize: 14, fontVariant: ["tabular-nums"] },
  empty: { color: "#6b7280", textAlign: "center" },
  err: { color: "#dc2626" },
});
