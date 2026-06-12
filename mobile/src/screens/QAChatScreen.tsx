// Q&A chat (US9). Asks the backend; renders the grounded answer plus the real
// records it's based on. Never shows an estimate — "not available" is honest.
// Styled as a chat: user questions are accent bubbles on the right, answers
// are cards on the left.

import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { apiPostJson } from "../api/client";
import { useT } from "../i18n";
import { fonts, radius, shadowFor, useTheme } from "../theme";

type Record = { merchant?: string; bill_date?: string | null; total_amount?: string | null; category?: string; item?: string };
type QAResponse = { path: "numeric" | "semantic" | "unanswerable"; answer?: string | null; records?: Record[]; executed_query?: string | null };
type Turn = { question: string; res?: QAResponse; error?: string };

const SUGGESTIONS = [
  "How much did I recharge last time?",
  "Groceries spend in March",
  "How much did I spend in total?",
  "Find the bill with cleaning supplies",
];

export function QAChatScreen() {
  const t = useT();
  const { c, mode } = useTheme();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setQuestion("");
    const idx = turns.length;
    setTurns((prev) => [...prev, { question: text }]);
    try {
      const res = await apiPostJson<QAResponse>("/qa", { question: text });
      setTurns((prev) => prev.map((turn, i) => (i === idx ? { ...turn, res } : turn)));
    } catch (e) {
      setTurns((prev) => prev.map((turn, i) => (i === idx ? { ...turn, error: String(e) } : turn)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.container, { backgroundColor: c.bg }]}>
      <FlatList
        data={turns}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          turns.length === 0 ? (
            <View style={styles.suggestions}>
              <Text style={[styles.hint, { color: c.muted }]}>{t("askPlaceholder")}</Text>
              {SUGGESTIONS.map((s) => (
                <Pressable
                  key={s}
                  style={({ pressed }) => [
                    styles.suggestion,
                    { backgroundColor: c.card, borderColor: c.line },
                    shadowFor(mode),
                    pressed && { opacity: 0.8 },
                  ]}
                  onPress={() => ask(s)}
                >
                  <Ionicons name="sparkles-outline" size={14} color={c.accent} />
                  <Text style={[styles.suggestionText, { color: c.text }]}>{s}</Text>
                </Pressable>
              ))}
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={styles.turn}>
            <View style={[styles.qBubble, { backgroundColor: c.accent }]}>
              <Text style={[styles.qText, { color: c.onAccent }]}>{item.question}</Text>
            </View>
            {item.error ? (
              <View style={[styles.aBubble, { backgroundColor: c.dangerSoft, borderColor: c.dangerSoft }]}>
                <Text style={{ color: c.danger, fontFamily: fonts.body }}>{item.error}</Text>
              </View>
            ) : item.res ? (
              <View
                style={[
                  styles.aBubble,
                  { backgroundColor: c.card, borderColor: c.line },
                  shadowFor(mode),
                  item.res.path === "unanswerable" && {
                    backgroundColor: c.warnSoft,
                    borderColor: c.warnSoft,
                  },
                ]}
              >
                <Text style={[styles.answerText, { color: c.text }]}>{item.res.answer}</Text>
                {(item.res.records ?? []).slice(0, 5).map((r, i) => (
                  <View key={i} style={styles.recordRow}>
                    <View style={[styles.recordDot, { backgroundColor: c.accent }]} />
                    <Text style={[styles.record, { color: c.muted }]} numberOfLines={1}>
                      {r.item ? `${r.item} — ₹${r.total_amount ?? "—"}${r.merchant ? ` · ${r.merchant}` : ""}`
                              : `${r.merchant} — ₹${r.total_amount ?? "—"}`}
                      {r.bill_date ? ` (${r.bill_date})` : ""}
                    </Text>
                  </View>
                ))}
                {item.res.path !== "unanswerable" && (
                  <Text style={[styles.path, { color: c.muted }]}>via {item.res.path} path</Text>
                )}
              </View>
            ) : (
              <View style={[styles.aBubble, styles.thinking, { backgroundColor: c.card, borderColor: c.line }]}>
                <ActivityIndicator size="small" color={c.accent} />
              </View>
            )}
          </View>
        )}
      />
      <View style={[styles.inputBar, { borderTopColor: c.line, backgroundColor: c.card }]}>
        <TextInput
          style={[styles.input, { borderColor: c.line, backgroundColor: c.well, color: c.text }]}
          value={question}
          onChangeText={setQuestion}
          placeholder={t("askPlaceholder")}
          placeholderTextColor={c.muted}
          onSubmitEditing={() => ask(question)}
          editable={!busy}
        />
        <Pressable
          style={({ pressed }) => [
            styles.send,
            { backgroundColor: c.accent },
            (busy || !question.trim()) && { opacity: 0.5 },
            pressed && { opacity: 0.8 },
          ]}
          onPress={() => ask(question)}
          disabled={busy}
        >
          <Ionicons name="send" size={18} color={c.onAccent} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  list: { padding: 16, gap: 16 },
  suggestions: { gap: 8 },
  hint: { marginBottom: 4, fontSize: 13, fontFamily: fonts.body },
  suggestion: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  suggestionText: { fontSize: 14, fontFamily: fonts.bodySemi, flex: 1 },
  turn: { gap: 8 },
  qBubble: {
    alignSelf: "flex-end",
    maxWidth: "85%",
    borderRadius: radius.lg,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  qText: { fontSize: 15, fontFamily: fonts.bodySemi },
  aBubble: {
    alignSelf: "flex-start",
    maxWidth: "92%",
    borderWidth: 1,
    borderRadius: radius.lg,
    borderTopLeftRadius: 4,
    padding: 12,
    gap: 5,
  },
  thinking: { paddingHorizontal: 22, paddingVertical: 14 },
  answerText: { fontSize: 15, lineHeight: 21, fontFamily: fonts.body },
  recordRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  recordDot: { width: 5, height: 5, borderRadius: 3 },
  record: { fontSize: 13, flex: 1, fontFamily: fonts.body },
  path: { fontSize: 11, marginTop: 4, fontFamily: fonts.body },
  inputBar: { flexDirection: "row", gap: 8, padding: 12, borderTopWidth: 1 },
  input: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontFamily: fonts.body,
  },
  send: {
    borderRadius: 22,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
});
