// Root entry point. Expo's AppEntry imports this default export.
import React from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Text, View } from "react-native";

import { RootNavigator } from "./src/navigation";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: string | null }
> {
  state = { error: null };
  static getDerivedStateFromError(e: unknown) {
    return { error: String(e) };
  }
  render() {
    if (this.state.error) {
      return (
        <View style={{ flex: 1, padding: 24, justifyContent: "center" }}>
          <Text style={{ color: "red", fontWeight: "bold", marginBottom: 8 }}>
            Render error:
          </Text>
          <Text style={{ fontFamily: "monospace", fontSize: 12 }}>
            {this.state.error}
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <RootNavigator />
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}
