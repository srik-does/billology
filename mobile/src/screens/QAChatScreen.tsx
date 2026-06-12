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
import { colors, radius, shadow } from "../theme";

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
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setQuestion("");
    const idx = turns.length;
    setTurns((t) => [...t, { question: text }]);
    try {
      const res = await apiPostJson<QAResponse>("/qa", { question: text });
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, res } : turn)));
    } catch (e) {
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, error: String(e) } : turn)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={turns}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          turns.length === 0 ? (
            <View style={styles.suggestions}>
              <Text style={styles.hint}>{t("askPlaceholder")}</Text>
              {SUGGESTIONS.map((s) => (
                <Pressable
                  key={s}
                  style={({ pressed }) => [styles.suggestion, pressed && { opacity: 0.8 }]}
                  onPress={() => ask(s)}
                >
                  <Ionicons name="sparkles-outline" size={14} color={colors.accent} />
                  <Text style={styles.suggestionText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={styles.turn}>
            <View style={styles.qBubble}>
              <Text style={styles.qText}>{item.question}</Text>
            </View>
            {item.error ? (
              <View style={[styles.aBubble, styles.errorBubble]}>
                <Text style={styles.err}>{item.error}</Text>
              </View>
            ) : item.res ? (
              <View style={[styles.aBubble, item.res.path === "unanswerable" && styles.unanswerable]}>
                <Text style={styles.answerText}>{item.res.answer}</Text>
                {(item.res.records ?? []).slice(0, 5).map((r, i) => (
                  <View key={i} style={styles.recordRow}>
                    <View style={styles.recordDot} />
                    <Text style={styles.record} numberOfLines={1}>
                      {r.item ? `${r.item} — ₹${r.total_amount ?? "—"}${r.merchant ? ` · ${r.merchant}` : ""}`
                              : `${r.merchant} — ₹${r.total_amount ?? "—"}`}
                      {r.bill_date ? ` (${r.bill_date})` : ""}
                    </Text>
                  </View>
                ))}
                {item.res.path !== "unanswerable" && (
                  <Text style={styles.path}>via {item.res.path} path</Text>
                )}
              </View>
            ) : (
              <View style={[styles.aBubble, styles.thinking]}>
                <ActivityIndicator size="small" color={colors.accent} />
              </View>
            )}
          </View>
        )}
      />
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={question}
          onChangeText={setQuestion}
          placeholder={t("askPlaceholder")}
          placeholderTextColor={colors.muted}
          onSubmitEditing={() => ask(question)}
          editable={!busy}
        />
        <Pressable
          style={({ pressed }) => [styles.send, (busy || !question.trim()) && { opacity: 0.5 }, pressed && { opacity: 0.8 }]}
          onPress={() => ask(question)}
          disabled={busy}
        >
          <Ionicons name="send" size={18} color="#ffffff" />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: 16, gap: 16 },
  suggestions: { gap: 8 },
  hint: { color: colors.muted, marginBottom: 4, fontSize: 13 },
  suggestion: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.card,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: 14,
    paddingVertical: 12,
    ...shadow,
  },
  suggestionText: { color: colors.text, fontSize: 14, fontWeight: "600", flex: 1 },
  turn: { gap: 8 },
  qBubble: {
    alignSelf: "flex-end",
    maxWidth: "85%",
    backgroundColor: colors.accent,
    borderRadius: radius.lg,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  qText: { color: "#ffffff", fontSize: 15, fontWeight: "600" },
  aBubble: {
    alignSelf: "flex-start",
    maxWidth: "92%",
    backgroundColor: colors.card,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    borderTopLeftRadius: 4,
    padding: 12,
    gap: 5,
    ...shadow,
  },
  unanswerable: { backgroundColor: colors.warnSoft, borderColor: colors.warnSoft },
  errorBubble: { backgroundColor: colors.dangerSoft, borderColor: colors.dangerSoft },
  thinking: { paddingHorizontal: 22, paddingVertical: 14 },
  answerText: { fontSize: 15, color: colors.text, lineHeight: 21 },
  recordRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  recordDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.accent },
  record: { fontSize: 13, color: colors.muted, flex: 1 },
  path: { fontSize: 11, color: colors.muted, marginTop: 4 },
  err: { color: colors.danger },
  inputBar: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.card,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: colors.text,
  },
  send: {
    backgroundColor: colors.accent,
    borderRadius: 22,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
});
