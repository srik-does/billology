// App navigation: a bottom tab bar (Add / Bills / Spending / Ask / Settings)
// with the Review → BillDetail flow pushed on a stack above it. Tabs put every
// primary destination one thumb-tap away instead of crowding header links.

import { Ionicons } from "@expo/vector-icons";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import {
  createNativeStackNavigator,
  type NativeStackScreenProps,
} from "@react-navigation/native-stack";

import { CaptureScreen } from "../screens/CaptureScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { BillDetailScreen } from "../screens/BillDetailScreen";
import { DashboardScreen } from "../screens/DashboardScreen";
import { QAChatScreen } from "../screens/QAChatScreen";
import { HistoryScreen } from "../screens/HistoryScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { useT } from "../i18n";
import { colors } from "../theme";

export type OriginalFile = { uri: string; name: string; type: string };

// One param list for the whole app: tab screens navigate to stack routes
// (Review/BillDetail) through the parent navigator.
export type RootStackParamList = {
  Tabs: undefined;
  Capture: undefined;
  Review: { candidate: any; originalFile?: OriginalFile };
  BillDetail: { bill: any };
  Dashboard: undefined;
  QAChat: undefined;
  History: undefined;
  Settings: undefined;
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

function HomeTabs() {
  const t = useT();
  return (
    <Tabs.Navigator
      initialRouteName="Capture"
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.card },
        headerShadowVisible: false,
        headerTitleStyle: { color: colors.text, fontWeight: "700" },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.line,
          height: 62,
          paddingBottom: 8,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
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
      originalFile={route.params.originalFile}
      onSaved={() => navigation.navigate("BillDetail", { bill: route.params.candidate })}
    />
  );
}

function BillDetailRoute({ route }: NativeStackScreenProps<RootStackParamList, "BillDetail">) {
  return <BillDetailScreen bill={route.params.bill} />;
}

export function RootNavigator() {
  const t = useT();
  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.card },
          headerShadowVisible: false,
          headerTitleStyle: { color: colors.text, fontWeight: "700" },
          headerTintColor: colors.accent,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="Tabs" component={HomeTabs} options={{ headerShown: false }} />
        <Stack.Screen name="Review" component={ReviewRoute} options={{ title: t("titleReview") }} />
        <Stack.Screen name="BillDetail" component={BillDetailRoute} options={{ title: t("titleBill") }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
