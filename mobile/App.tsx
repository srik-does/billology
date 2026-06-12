// Root entry point. Expo's AppEntry imports this default export.
// Loads the brand fonts, provides the theme, and plays the wordmark splash:
// "Billology" fades in, holds, and fades away to reveal the landing screen.

import React, { useEffect, useMemo, useRef, useState } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Animated, Easing, StatusBar, StyleSheet, Text, View } from "react-native";
import { useFonts } from "expo-font";
import {
  Fraunces_600SemiBold,
  Fraunces_700Bold,
  Fraunces_700Bold_Italic,
} from "@expo-google-fonts/fraunces";
import {
  Manrope_500Medium,
  Manrope_600SemiBold,
  Manrope_700Bold,
  Manrope_800ExtraBold,
} from "@expo-google-fonts/manrope";

import { RootNavigator } from "./src/navigation";
import { palettes, ThemeContext, type Theme } from "./src/theme";
import { updateSettings, useSettings } from "./src/store";

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

/** Brand splash: the styled wordmark fades in, holds, then fades away. */
function SplashOverlay({ onDone }: { onDone: () => void }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const rise = useRef(new Animated.Value(10)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 550,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(rise, {
          toValue: 0,
          duration: 550,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.delay(900),
      Animated.timing(opacity, {
        toValue: 0,
        duration: 450,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start(({ finished }) => finished && onDone());
  }, [onDone, opacity, rise]);

  return (
    <View style={splash.cover} pointerEvents="none">
      <Animated.View style={{ opacity, transform: [{ translateY: rise }], alignItems: "center" }}>
        <Text style={splash.wordmark}>
          <Text style={splash.bill}>Bill</Text>
          <Text style={splash.ology}>ology</Text>
        </Text>
        <View style={splash.rule} />
        <Text style={splash.tag}>every number, straight from the bill</Text>
      </Animated.View>
    </View>
  );
}

const splash = StyleSheet.create({
  cover: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#0D2B28",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10,
  },
  wordmark: { fontSize: 52, fontFamily: "Fraunces_700Bold_Italic", letterSpacing: 0.5 },
  bill: { color: "#F1ECE2" },
  ology: { color: "#5CD6C3" },
  rule: { width: 64, height: 3, borderRadius: 2, backgroundColor: "#E9A23B", marginTop: 14 },
  tag: {
    marginTop: 12,
    color: "rgba(241,236,226,0.75)",
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    letterSpacing: 0.6,
  },
});

function ThemedApp() {
  const { theme: mode } = useSettings();
  const [showSplash, setShowSplash] = useState(true);

  const theme: Theme = useMemo(
    () => ({
      mode,
      c: palettes[mode],
      toggle: () => updateSettings({ theme: mode === "light" ? "dark" : "light" }),
    }),
    [mode]
  );

  return (
    <ThemeContext.Provider value={theme}>
      <StatusBar barStyle={mode === "light" ? "dark-content" : "light-content"} />
      <RootNavigator />
      {showSplash && <SplashOverlay onDone={() => setShowSplash(false)} />}
    </ThemeContext.Provider>
  );
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Fraunces_600SemiBold,
    Fraunces_700Bold,
    Fraunces_700Bold_Italic,
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Manrope_800ExtraBold,
  });

  // Hold a blank brand-colored frame until fonts arrive (sub-second), so the
  // wordmark never flashes in a fallback font.
  if (!fontsLoaded) {
    return <View style={{ flex: 1, backgroundColor: "#0D2B28" }} />;
  }

  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <ThemedApp />
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}
