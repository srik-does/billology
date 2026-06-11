// App navigation. Capture is the entry point; it pushes Review with the
// extracted candidate, Review pushes BillDetail on save, and History /
// Dashboard / Q&A / Settings are reachable from the Capture header.

import { NavigationContainer } from "@react-navigation/native";
import {
  createNativeStackNavigator,
  type NativeStackScreenProps,
} from "@react-navigation/native-stack";
import { Pressable, Text, View } from "react-native";

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

export type RootStackParamList = {
  Capture: undefined;
  Review: { candidate: any; originalFile?: OriginalFile };
  BillDetail: { bill: any };
  Dashboard: undefined;
  QAChat: undefined;
  History: undefined;
  Settings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

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

function HeaderLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      <Text style={{ color: colors.accent, fontWeight: "600", fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}

export function RootNavigator() {
  const t = useT();
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="Capture"
        screenOptions={{
          headerStyle: { backgroundColor: colors.card },
          headerTitleStyle: { color: colors.text, fontWeight: "700" },
          headerTintColor: colors.accent,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen
          name="Capture"
          component={CaptureScreen}
          options={({ navigation }) => ({
            title: t("appTitle"),
            headerRight: () => (
              <View style={{ flexDirection: "row", gap: 14, alignItems: "center" }}>
                <HeaderLink label={t("navBills")} onPress={() => navigation.navigate("History")} />
                <HeaderLink label={t("navSpending")} onPress={() => navigation.navigate("Dashboard")} />
                <HeaderLink label={t("navAsk")} onPress={() => navigation.navigate("QAChat")} />
                <HeaderLink label={t("navSettings")} onPress={() => navigation.navigate("Settings")} />
              </View>
            ),
          })}
        />
        <Stack.Screen name="Review" component={ReviewRoute} options={{ title: t("titleReview") }} />
        <Stack.Screen name="BillDetail" component={BillDetailRoute} options={{ title: t("titleBill") }} />
        <Stack.Screen name="Dashboard" component={DashboardScreen} options={{ title: t("titleSpending") }} />
        <Stack.Screen name="QAChat" component={QAChatScreen} options={{ title: t("titleAsk") }} />
        <Stack.Screen name="History" component={HistoryScreen} options={{ title: t("titleHistory") }} />
        <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: t("titleSettings") }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
