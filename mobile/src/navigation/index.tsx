// App navigation: a bottom tab bar (Add / Bills / Spending / Ask / Settings)
// with the Review → BillDetail flow pushed on a stack above it. Tabs put every
// primary destination one thumb-tap away instead of crowding header links.
// Every header carries the light/dark toggle; Help lives on the stack.

import { Ionicons } from "@expo/vector-icons";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import {
  createNativeStackNavigator,
  type NativeStackScreenProps,
} from "@react-navigation/native-stack";
import { Pressable } from "react-native";

import { CaptureScreen } from "../screens/CaptureScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { BillDetailScreen } from "../screens/BillDetailScreen";
import { DashboardScreen } from "../screens/DashboardScreen";
import { QAChatScreen } from "../screens/QAChatScreen";
import { HistoryScreen } from "../screens/HistoryScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { HelpScreen } from "../screens/HelpScreen";
import { useT } from "../i18n";
import { fonts, useTheme } from "../theme";

export type OriginalFile = { uri: string; name: string; type: string };

// One param list for the whole app: tab screens navigate to stack routes
// (Review/BillDetail/Help) through the parent navigator.
export type RootStackParamList = {
  Tabs: undefined;
  Capture: undefined;
  Review: { candidate: any; originalFiles?: OriginalFile[] };
  BillDetail: { bill: any };
  Dashboard: undefined;
  QAChat: undefined;
  History: undefined;
  Settings: undefined;
  Help: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tabs = createBottomTabNavigator<RootStackParamList>();

const TAB_ICONS: Record<string, [keyof typeof Ionicons.glyphMap, keyof typeof Ionicons.glyphMap]> = {
  Capture: ["add-circle", "add-circle-outline"],
  History: ["receipt", "receipt-outline"],
  Dashboard: ["pie-chart", "pie-chart-outline"],
  QAChat: ["chatbubbles", "chatbubbles-outline"],
  Settings: ["settings", "settings-outline"],
};

function ThemeToggle() {
  const { mode, toggle, c } = useTheme();
  return (
    <Pressable
      onPress={toggle}
      hitSlop={10}
      style={({ pressed }) => [{ paddingHorizontal: 6 }, pressed && { opacity: 0.6 }]}
      accessibilityLabel="Toggle light/dark theme"
    >
      <Ionicons name={mode === "light" ? "moon-outline" : "sunny-outline"} size={21} color={c.accent} />
    </Pressable>
  );
}

function HomeTabs() {
  const t = useT();
  const { c } = useTheme();
  return (
    <Tabs.Navigator
      initialRouteName="Capture"
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: c.card },
        headerShadowVisible: false,
        headerTitleStyle: { color: c.text, fontFamily: fonts.bodyHeavy, fontSize: 17 },
        headerRight: () => <ThemeToggle />,
        headerRightContainerStyle: { paddingRight: 10 },
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.muted,
        // Don't let the tab bar ride on top of the keyboard (Android) — it
        // would stack under the input and eat vertical space while typing.
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          backgroundColor: c.card,
          borderTopColor: c.line,
          height: 62,
          paddingBottom: 8,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 11, fontFamily: fonts.bodySemi },
        tabBarIcon: ({ color, size, focused }) => (
          <Ionicons
            name={TAB_ICONS[route.name]?.[focused ? 0 : 1] ?? "ellipse"}
            size={size}
            color={color}
          />
        ),
      })}
    >
      <Tabs.Screen
        name="Capture"
        component={CaptureScreen}
        options={{ title: t("appTitle"), tabBarLabel: t("navAdd") }}
      />
      <Tabs.Screen
        name="History"
        component={HistoryScreen}
        options={{ title: t("titleHistory"), tabBarLabel: t("navBills") }}
      />
      <Tabs.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ title: t("titleSpending"), tabBarLabel: t("navSpending") }}
      />
      <Tabs.Screen
        name="QAChat"
        component={QAChatScreen}
        options={{ title: t("titleAsk"), tabBarLabel: t("navAsk") }}
      />
      <Tabs.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ title: t("titleSettings"), tabBarLabel: t("titleSettings") }}
      />
    </Tabs.Navigator>
  );
}

// Review needs the candidate from route params; on save, show the bill detail.
function ReviewRoute({ route, navigation }: NativeStackScreenProps<RootStackParamList, "Review">) {
  return (
    <ReviewScreen
      candidate={route.params.candidate}
      originalFiles={route.params.originalFiles}
      onSaved={() => navigation.navigate("BillDetail", { bill: route.params.candidate })}
    />
  );
}

function BillDetailRoute({ route }: NativeStackScreenProps<RootStackParamList, "BillDetail">) {
  return <BillDetailScreen bill={route.params.bill} />;
}

export function RootNavigator() {
  const t = useT();
  const { c, mode } = useTheme();

  const navTheme = {
    ...DefaultTheme,
    dark: mode === "dark",
    colors: {
      ...DefaultTheme.colors,
      primary: c.accent,
      background: c.bg,
      card: c.card,
      text: c.text,
      border: c.line,
    },
  };

  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: c.card },
          headerShadowVisible: false,
          headerTitleStyle: { color: c.text, fontFamily: fonts.bodyHeavy, fontSize: 17 },
          headerTintColor: c.accent,
          contentStyle: { backgroundColor: c.bg },
        }}
      >
        <Stack.Screen name="Tabs" component={HomeTabs} options={{ headerShown: false }} />
        <Stack.Screen name="Review" component={ReviewRoute} options={{ title: t("titleReview") }} />
        <Stack.Screen name="BillDetail" component={BillDetailRoute} options={{ title: t("titleBill") }} />
        <Stack.Screen name="Help" component={HelpScreen} options={{ title: t("helpTitle") }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
