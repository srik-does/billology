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
import { fonts, useTheme } from "../theme";

type CategoryRow = { category: string; total: string };
type MonthRow = { month: string; total: string };
type BillRow = { id: string; merchant?: string | null; total_amount?: string | null };

const inr = (n: number) =>
  "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });

const ym = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

// --- Nice y-axis (#7): standard 1/2/5 × 10^k steps -------------------------
// Instead of whatever maxValue/4 happens to be (e.g. 437.25, 874.5 …), the
// axis climbs in familiar steps — 100, 200, 500, 1000 — sized to the data.
function niceStep(rough: number): number {
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(rough, 1))));
  for (const m of [1, 2, 5, 10]) {
    if (rough <= m * pow) return m * pow;
  }
  return 10 * pow;
}

function niceAxis(rawMax: number): { maxValue: number; sections: number; labels: string[] } {
  if (rawMax <= 0) return { maxValue: 400, sections: 4, labels: ["0", "100", "200", "300", "400"] };
  const step = niceStep(rawMax / 4); // aim for ~4 bands
  const sections = Math.max(1, Math.ceil(rawMax / step));
  const maxValue = step * sections;
  const labels = Array.from({ length: sections + 1 }, (_, i) =>
    (step * i).toLocaleString("en-IN")
  );
  return { maxValue, sections, labels };
}

export function DashboardScreen() {
  const t = useT();
  const { c } = useTheme();
  const PALETTE = c.series;
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
        <Text style={[styles.err, { color: c.danger }]}>{error}</Text>
        <View style={{ marginTop: 12 }}>
          <Chip label={t("retry")} onPress={load} />
        </View>
      </Centered>
    );
  }
  if (!byCategory || !monthly) {
    return <Centered><ActivityIndicator color={c.accent} /></Centered>;
  }

  const hasData = byCategory.length > 0 || monthly.length > 0;
  if (!hasData) {
    return <Centered><Text style={[styles.empty, { color: c.muted }]}>{t("noBillsYet")}</Text></Centered>;
  }

  // Stat cards: current month, delta vs previous month, top category.
  const now = new Date();
  const cur = Number(monthly.find((m) => m.month === ym(now))?.total ?? 0);
  const prevMonth = ym(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const prev = Number(monthly.find((m) => m.month === prevMonth)?.total ?? 0);
  const deltaPct = prev > 0 ? ((cur - prev) / prev) * 100 : null;
  const topCat = byCategory[0];

  const pieData = byCategory.map((cRow, i) => ({
    value: Number(cRow.total),
    color: PALETTE[i % PALETTE.length],
    text: cRow.category,
  }));
  const total = byCategory.reduce((s, cRow) => s + Number(cRow.total), 0);

  const barData = monthly.map((m) => ({
    value: Number(m.total),
    label: m.month.slice(5), // MM
  }));
  const axis = niceAxis(Math.max(...barData.map((d) => d.value), 0));

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
      style={{ backgroundColor: c.bg }}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
    >
      <View style={styles.statsRow}>
        <View style={[styles.stat, { backgroundColor: c.card, borderColor: c.line }]}>
          <Text style={[styles.statLabel, { color: c.muted }]}>{t("thisMonth")}</Text>
          <Text style={[styles.statValue, { color: c.text }]}>{inr(cur)}</Text>
          {deltaPct !== null && (
            <Text style={[styles.delta, { color: deltaPct >= 0 ? c.danger : c.good }]}>
              {deltaPct >= 0 ? "▲" : "▼"} {Math.abs(deltaPct).toFixed(0)}%{" "}
              <Text style={[styles.deltaMuted, { color: c.muted }]}>{t("vsLastMonth")}</Text>
            </Text>
          )}
        </View>
        {topCat && (
          <View style={[styles.stat, { backgroundColor: c.card, borderColor: c.line }]}>
            <Text style={[styles.statLabel, { color: c.muted }]}>{t("topCategory")}</Text>
            <Text style={[styles.statValueSmall, { color: c.text }]} numberOfLines={1}>
              {topCat.category}
            </Text>
            <Text style={[styles.deltaMuted, { color: c.muted }]}>{inr(Number(topCat.total))}</Text>
          </View>
        )}
        <View style={[styles.stat, { backgroundColor: c.card, borderColor: c.line }]}>
          <Text style={[styles.statLabel, { color: c.muted }]}>{t("navBills")}</Text>
          <Text style={[styles.statValue, { color: c.text }]}>{bills.length}</Text>
        </View>
      </View>

      <Text style={[styles.section, { color: c.muted }]}>{t("byCategory")}</Text>
      <View style={styles.center}>
        <PieChart
          data={pieData}
          donut
          radius={110}
          innerRadius={70}
          backgroundColor={c.bg}
          centerLabelComponent={() => (
            <View style={styles.center}>
              <Text style={[styles.totalLabel, { color: c.muted }]}>{t("total")}</Text>
              <Text style={[styles.totalValue, { color: c.text }]}>{inr(total)}</Text>
            </View>
          )}
        />
      </View>
      <View style={styles.legend}>
        {byCategory.map((cRow, i) => (
          <View key={cRow.category} style={styles.legendRow}>
            <View style={[styles.swatch, { backgroundColor: PALETTE[i % PALETTE.length] }]} />
            <Text style={[styles.legendText, { color: c.text }]}>{cRow.category}</Text>
            <Text style={[styles.legendValue, { color: c.text }]}>{inr(Number(cRow.total))}</Text>
          </View>
        ))}
      </View>

      <Text style={[styles.section, { color: c.muted }]}>{t("monthlyTrend")}</Text>
      <BarChart
        data={barData}
        frontColor={c.accent}
        barWidth={28}
        spacing={18}
        yAxisThickness={0}
        xAxisThickness={0}
        maxValue={axis.maxValue}
        noOfSections={axis.sections}
        yAxisLabelTexts={axis.labels}
        yAxisTextStyle={{ color: c.muted, fontSize: 11, fontFamily: fonts.body }}
        xAxisLabelTextStyle={{ color: c.muted, fontSize: 11, fontFamily: fonts.body }}
        rulesColor={c.line}
        isAnimated
        animationDuration={700}
        barBorderTopLeftRadius={4}
        barBorderTopRightRadius={4}
      />

      {topMerchants.length > 0 && (
        <>
          <Text style={[styles.section, { color: c.muted }]}>{t("topMerchants")}</Text>
          <View style={styles.merchants}>
            {topMerchants.map(([name, value], i) => (
              <View key={name} style={styles.merchantRow}>
                <View style={styles.merchantHead}>
                  <Text style={[styles.legendText, { color: c.text }]} numberOfLines={1}>
                    {name}
                  </Text>
                  <Text style={[styles.legendValue, { color: c.text }]}>{inr(value)}</Text>
                </View>
                <View style={[styles.track, { backgroundColor: c.line }]}>
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
  const { c } = useTheme();
  return <View style={[styles.centeredFull, { backgroundColor: c.bg }]}>{children}</View>;
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 10, paddingBottom: 32 },
  centeredFull: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  center: { alignItems: "center", justifyContent: "center" },
  statsRow: { flexDirection: "row", gap: 10, flexWrap: "wrap", marginTop: 6 },
  stat: { flexGrow: 1, flexBasis: 100, borderWidth: 1, borderRadius: 12, padding: 12 },
  statLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, fontFamily: fonts.bodySemi },
  statValue: { fontSize: 18, fontFamily: fonts.display, marginTop: 4, fontVariant: ["tabular-nums"] },
  statValueSmall: { fontSize: 15, fontFamily: fonts.bodyBold, marginTop: 4 },
  delta: { fontSize: 12, marginTop: 2, fontFamily: fonts.bodySemi },
  deltaMuted: { fontSize: 12, fontFamily: fonts.body },
  section: {
    marginTop: 18,
    fontSize: 13,
    fontFamily: fonts.bodyBold,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  totalLabel: { fontSize: 12, fontFamily: fonts.body },
  totalValue: { fontFamily: fonts.display, fontSize: 16 },
  legend: { marginTop: 12, gap: 6 },
  legendRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  legendText: { flex: 1, fontSize: 14, fontFamily: fonts.body },
  legendValue: { fontSize: 14, fontFamily: fonts.bodySemi, fontVariant: ["tabular-nums"] },
  merchants: { gap: 10, marginTop: 4 },
  merchantRow: { gap: 4 },
  merchantHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  track: { borderRadius: 4, height: 8 },
  fill: { height: 8, borderRadius: 4 },
  empty: { textAlign: "center", fontFamily: fonts.body },
  err: { textAlign: "center", fontFamily: fonts.body },
});
