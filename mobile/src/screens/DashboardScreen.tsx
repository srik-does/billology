// Spending dashboard (US8). Views over saved records only: stat cards (this
// month, change vs last month, top category), category donut, animated monthly
// trend, and top merchants. Figures come from the backend's SQL-style
// aggregates — no client-side estimation; the merchant rollup only sums real
// saved totals.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { BarChart, PieChart } from "react-native-gifted-charts";

import { apiGet } from "../api/client";
import { Chip } from "../components/UI";
import { useT } from "../i18n";
import { colors } from "../theme";

type CategoryRow = { category: string; total: string };
type MonthRow = { month: string; total: string };
type BillRow = { id: string; merchant?: string | null; total_amount?: string | null };

const PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#db2777", "#7c3aed", "#0891b2", "#9ca3af"];

const inr = (n: number) =>
  "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });

const ym = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

export function DashboardScreen() {
  const t = useT();
  const [byCategory, setByCategory] = useState<CategoryRow[] | null>(null);
  const [monthly, setMonthly] = useState<MonthRow[] | null>(null);
  const [bills, setBills] = useState<BillRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [cats, months, billRows] = await Promise.all([
        apiGet<CategoryRow[]>("/dashboard/by-category"),
        apiGet<MonthRow[]>("/dashboard/monthly"),
        apiGet<BillRow[]>("/bills"),
      ]);
      setByCategory([...cats].sort((a, b) => Number(b.total) - Number(a.total)));
      setMonthly(months);
      setBills(billRows);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  if (error) {
    return (
      <Centered>
        <Text style={styles.err}>{error}</Text>
        <View style={{ marginTop: 12 }}>
          <Chip label={t("retry")} onPress={load} />
        </View>
      </Centered>
    );
  }
  if (!byCategory || !monthly) {
    return <Centered><ActivityIndicator /></Centered>;
  }

  const hasData = byCategory.length > 0 || monthly.length > 0;
  if (!hasData) {
    return <Centered><Text style={styles.empty}>{t("noBillsYet")}</Text></Centered>;
  }

  // Stat cards: current month, delta vs previous month, top category.
  const now = new Date();
  const cur = Number(monthly.find((m) => m.month === ym(now))?.total ?? 0);
  const prevMonth = ym(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const prev = Number(monthly.find((m) => m.month === prevMonth)?.total ?? 0);
  const deltaPct = prev > 0 ? ((cur - prev) / prev) * 100 : null;
  const topCat = byCategory[0];

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

  // Top merchants from saved bills (small dataset; aggregated client-side).
  const byMerchant = new Map<string, number>();
  for (const b of bills) {
    const name = b.merchant || "—";
    byMerchant.set(name, (byMerchant.get(name) ?? 0) + Number(b.total_amount ?? 0));
  }
  const topMerchants = [...byMerchant.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const merchantMax = topMerchants.length ? topMerchants[0][1] : 0;

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
    >
      <Text style={styles.title}>{t("titleSpending")}</Text>

      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>{t("thisMonth")}</Text>
          <Text style={styles.statValue}>{inr(cur)}</Text>
          {deltaPct !== null && (
            <Text style={[styles.delta, deltaPct >= 0 ? styles.deltaUp : styles.deltaDown]}>
              {deltaPct >= 0 ? "▲" : "▼"} {Math.abs(deltaPct).toFixed(0)}%{" "}
              <Text style={styles.deltaMuted}>{t("vsLastMonth")}</Text>
            </Text>
          )}
        </View>
        {topCat && (
          <View style={styles.stat}>
            <Text style={styles.statLabel}>{t("topCategory")}</Text>
            <Text style={styles.statValueSmall} numberOfLines={1}>{topCat.category}</Text>
            <Text style={styles.deltaMuted}>{inr(Number(topCat.total))}</Text>
          </View>
        )}
        <View style={styles.stat}>
          <Text style={styles.statLabel}>{t("navBills")}</Text>
          <Text style={styles.statValue}>{bills.length}</Text>
        </View>
      </View>

      <Text style={styles.section}>{t("byCategory")}</Text>
      <View style={styles.center}>
        <PieChart
          data={pieData}
          donut
          radius={110}
          innerRadius={70}
          centerLabelComponent={() => (
            <View style={styles.center}>
              <Text style={styles.totalLabel}>{t("total")}</Text>
              <Text style={styles.totalValue}>{inr(total)}</Text>
            </View>
          )}
        />
      </View>
      <View style={styles.legend}>
        {byCategory.map((c, i) => (
          <View key={c.category} style={styles.legendRow}>
            <View style={[styles.swatch, { backgroundColor: PALETTE[i % PALETTE.length] }]} />
            <Text style={styles.legendText}>{c.category}</Text>
            <Text style={styles.legendValue}>{inr(Number(c.total))}</Text>
          </View>
        ))}
      </View>

      <Text style={styles.section}>{t("monthlyTrend")}</Text>
      <BarChart
        data={barData}
        frontColor={colors.accent}
        barWidth={28}
        spacing={18}
        yAxisThickness={0}
        xAxisThickness={0}
        noOfSections={4}
        isAnimated
        animationDuration={700}
        barBorderTopLeftRadius={4}
        barBorderTopRightRadius={4}
      />

      {topMerchants.length > 0 && (
        <>
          <Text style={styles.section}>{t("topMerchants")}</Text>
          <View style={styles.merchants}>
            {topMerchants.map(([name, value], i) => (
              <View key={name} style={styles.merchantRow}>
                <View style={styles.merchantHead}>
                  <Text style={styles.legendText} numberOfLines={1}>{name}</Text>
                  <Text style={styles.legendValue}>{inr(value)}</Text>
                </View>
                <View style={styles.track}>
                  <View
                    style={[
                      styles.fill,
                      {
                        backgroundColor: PALETTE[i % PALETTE.length],
                        width: `${merchantMax > 0 ? Math.max(3, Math.round((value / merchantMax) * 100)) : 0}%`,
                      },
                    ]}
                  />
                </View>
              </View>
            ))}
          </View>
        </>
      )}
    </ScrollView>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <View style={styles.centeredFull}>{children}</View>;
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 10, paddingBottom: 32 },
  centeredFull: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  center: { alignItems: "center", justifyContent: "center" },
  title: { fontSize: 22, fontWeight: "700" },
  statsRow: { flexDirection: "row", gap: 10, flexWrap: "wrap", marginTop: 6 },
  stat: {
    flexGrow: 1, flexBasis: 100, backgroundColor: colors.card, borderColor: colors.line,
    borderWidth: 1, borderRadius: 12, padding: 12,
  },
  statLabel: {
    color: colors.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5,
  },
  statValue: { fontSize: 18, fontWeight: "700", marginTop: 4, fontVariant: ["tabular-nums"] },
  statValueSmall: { fontSize: 15, fontWeight: "700", marginTop: 4 },
  delta: { fontSize: 12, marginTop: 2 },
  deltaUp: { color: "#dc2626" },
  deltaDown: { color: "#16a34a" },
  deltaMuted: { color: colors.muted, fontSize: 12 },
  section: {
    marginTop: 18, fontSize: 13, fontWeight: "700", color: colors.muted,
    textTransform: "uppercase",
  },
  totalLabel: { color: colors.muted, fontSize: 12 },
  totalValue: { fontWeight: "700", fontSize: 16 },
  legend: { marginTop: 12, gap: 6 },
  legendRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  legendText: { flex: 1, fontSize: 14 },
  legendValue: { fontSize: 14, fontVariant: ["tabular-nums"] },
  merchants: { gap: 10, marginTop: 4 },
  merchantRow: { gap: 4 },
  merchantHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  track: { backgroundColor: colors.line, borderRadius: 4, height: 8 },
  fill: { height: 8, borderRadius: 4 },
  empty: { color: colors.muted, textAlign: "center" },
  err: { color: "#dc2626", textAlign: "center" },
});
