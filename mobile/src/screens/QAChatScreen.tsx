// Q&A chat (US9). Asks the backend; renders the grounded answer plus the real
// records it's based on. Never shows an estimate — "not available" is honest.

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

import { apiPostJson } from "../api/client";

type Record = { merchant?: string; bill_date?: string | null; total_amount?: string | null; category?: string };
type QAResponse = { path: "numeric" | "semantic" | "unanswerable"; answer?: string | null; records?: Record[]; executed_query?: string | null };
type Turn = { question: string; res?: QAResponse; error?: string };

const SUGGESTIONS = [
  "How much did I recharge last time?",
  "Groceries spend in March",
  "How much did I spend in total?",
  "Find the bill with cleaning supplies",
];

export function QAChatScreen() {
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
              <Text style={styles.hint}>Ask about your spending:</Text>
              {SUGGESTIONS.map((s) => (
                <Pressable key={s} style={styles.chip} onPress={() => ask(s)}>
                  <Text style={styles.chipText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={styles.turn}>
            <Text style={styles.q}>{item.question}</Text>
            {item.error ? (
              <Text style={styles.err}>{item.error}</Text>
            ) : item.res ? (
              <View style={[styles.answer, item.res.path === "unanswerable" && styles.unanswerable]}>
                <Text style={styles.answerText}>{item.res.answer}</Text>
                {(item.res.records ?? []).slice(0, 5).map((r, i) => (
                  <Text key={i} style={styles.record}>
                    • {r.merchant} — ₹{r.total_amount ?? "—"} {r.bill_date ? `(${r.bill_date})` : ""}
                  </Text>
                ))}
                {item.res.path !== "unanswerable" && (
                  <Text style={styles.path}>via {item.res.path} path</Text>
                )}
              </View>
            ) : (
              <ActivityIndicator style={{ alignSelf: "flex-start", marginTop: 6 }} />
            )}
          </View>
        )}
      />
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={question}
          onChangeText={setQuestion}
          placeholder="Ask about your spending…"
          onSubmitEditing={() => ask(question)}
          editable={!busy}
        />
        <Pressable style={styles.send} onPress={() => ask(question)} disabled={busy}>
          <Text style={styles.sendText}>Ask</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  list: { padding: 16, gap: 14 },
  suggestions: { gap: 8 },
  hint: { color: "#6b7280", marginBottom: 4 },
  chip: { backgroundColor: "#eff6ff", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8 },
  chipText: { color: "#2563eb" },
  turn: { gap: 6 },
  q: { fontWeight: "700", fontSize: 15 },
  answer: { backgroundColor: "#f3f4f6", borderRadius: 8, padding: 10, gap: 3 },
  unanswerable: { backgroundColor: "#fef2f2" },
  answerText: { fontSize: 15, color: "#111827" },
  record: { fontSize: 13, color: "#374151" },
  path: { fontSize: 11, color: "#9ca3af", marginTop: 4 },
  err: { color: "#dc2626" },
  inputBar: { flexDirection: "row", gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: "#e5e7eb" },
  input: { flex: 1, borderWidth: 1, borderColor: "#d1d5db", borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  send: { backgroundColor: "#2563eb", borderRadius: 20, paddingHorizontal: 18, justifyContent: "center" },
  sendText: { color: "#fff", fontWeight: "700" },
});
