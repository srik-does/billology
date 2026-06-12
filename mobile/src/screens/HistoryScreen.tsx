// Bill history (user request): list saved bills newest-first, search by
// merchant, filter by category, open a bill's detail, delete one (long-press)
// or clear everything (for demoing with fresh data).

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { apiDelete, apiGet } from "../api/client";
import { Btn, Chip } from "../components/UI";
import { useT } from "../i18n";
import type { RootStackParamList } from "../navigation";
import { fonts, SEED_CATEGORIES, shadowFor, useTheme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "History">;

type Row = {
  id: string;
  merchant: string | null;
  bill_date: string | null;
  total_amount: string | null;
  category: string | null;
};

export function HistoryScreen() {
  const navigation = useNavigation<Nav>();
  const t = useT();
  const { c, mode } = useTheme();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRows(await apiGet<Row[]>("/bills"));
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function openBill(row: Row) {
    try {
      const bill = await apiGet<object>(`/bills/${row.id}`);
      navigation.navigate("BillDetail", { bill });
    } catch (e) {
      Alert.alert("Couldn't load bill", String(e));
    }
  }

  function confirmDeleteOne(row: Row) {
    Alert.alert(
      "Delete this bill?",
      `${row.merchant ?? "Bill"} — ₹${row.total_amount ?? "—"}`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await apiDelete(`/bills/${row.id}`);
              await load();
            } catch (e) {
              Alert.alert("Delete failed", String(e));
            }
          },
        },
      ]
    );
  }

  function confirmClearAll() {
    Alert.alert(
      "Clear ALL data?",
      "This permanently deletes every saved bill (including seeded demo data).",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete everything",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await apiDelete<{ deleted: number }>("/bills");
              Alert.alert("Cleared", `${res.deleted} bill(s) deleted.`);
              await load();
            } catch (e) {
              Alert.alert("Clear failed", String(e));
            }
          },
        },
      ]
    );
  }

  const filtered = (rows ?? []).filter((r) => {
    if (q && !(r.merchant ?? "").toLowerCase().includes(q.trim().toLowerCase())) return false;
    if (cat && (r.category ?? "") !== cat) return false;
    return true;
  });

  if (error) {
    return (
      <View style={[styles.center, { backgroundColor: c.bg }]}>
        <Text style={{ color: c.danger, textAlign: "center", fontFamily: fonts.body }}>{error}</Text>
        <Btn title={t("retry")} onPress={load} style={{ marginTop: 12 }} />
      </View>
    );
  }
  if (rows === null) {
    return (
      <View style={[styles.center, { backgroundColor: c.bg }]}>
        <ActivityIndicator color={c.accent} />
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: c.bg }]}>
      <TextInput
        style={[styles.search, { backgroundColor: c.card, borderColor: c.line, color: c.text }]}
        placeholder={t("searchMerchant")}
        placeholderTextColor={c.muted}
        value={q}
        onChangeText={setQ}
      />
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={["__all__", ...SEED_CATEGORIES]}
        keyExtractor={(item) => item}
        style={styles.chips}
        contentContainerStyle={{ gap: 8 }}
        renderItem={({ item }) => (
          <Chip
            label={item === "__all__" ? t("all") : item}
            active={item === "__all__" ? cat === null : cat === item}
            onPress={() => setCat(item === "__all__" ? null : item)}
          />
        )}
      />
      <FlatList
        data={filtered}
        keyExtractor={(r) => r.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        contentContainerStyle={{ gap: 8, paddingBottom: 12 }}
        ListEmptyComponent={
          <Text style={[styles.empty, { color: c.muted }]}>
            {rows.length === 0 ? t("noBillsYet") : t("noMatch")}
          </Text>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => openBill(item)}
            onLongPress={() => confirmDeleteOne(item)}
            style={({ pressed }) => [
              styles.row,
              { backgroundColor: c.card, borderColor: c.line },
              shadowFor(mode),
              pressed && { opacity: 0.7 },
            ]}
          >
            <View style={[styles.avatar, { backgroundColor: c.accentSoft }]}>
              <Text style={[styles.avatarText, { color: c.accent }]}>
                {(item.merchant ?? "?").trim().charAt(0).toUpperCase() || "?"}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.merchant, { color: c.text }]} numberOfLines={1}>
                {item.merchant ?? "Unknown merchant"}
              </Text>
              <View style={styles.metaRow}>
                <Text style={[styles.meta, { color: c.muted }]}>{item.bill_date ?? "—"}</Text>
                {item.category ? (
                  <View style={[styles.pill, { backgroundColor: c.accentSoft }]}>
                    <Text style={[styles.pillText, { color: c.accent }]}>{item.category}</Text>
                  </View>
                ) : null}
              </View>
            </View>
            <Text style={[styles.amount, { color: c.text }]}>₹{item.total_amount ?? "—"}</Text>
          </Pressable>
        )}
      />
      <Text style={[styles.hint, { color: c.muted }]}>{t("historyHint")}</Text>
      <Btn title={t("clearAll")} variant="danger" onPress={confirmClearAll} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 14, gap: 10 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  search: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    fontFamily: fonts.body,
  },
  chips: { flexGrow: 0 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: 1,
    borderRadius: 16,
    padding: 14,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { fontFamily: fonts.display, fontSize: 16 },
  merchant: { fontSize: 15, fontFamily: fonts.bodyBold },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 3 },
  meta: { fontSize: 12.5, fontFamily: fonts.body },
  pill: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  pillText: { fontSize: 11, fontFamily: fonts.bodyBold },
  amount: { fontSize: 15, fontFamily: fonts.bodySemi, fontVariant: ["tabular-nums"] },
  empty: { textAlign: "center", marginTop: 32, paddingHorizontal: 24, fontFamily: fonts.body },
  hint: { textAlign: "center", fontSize: 12, fontFamily: fonts.body },
});
