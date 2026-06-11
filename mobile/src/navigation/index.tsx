// App navigation. Capture is the entry point; it pushes Review with the
// extracted candidate, Review pushes BillDetail on save, and Dashboard / Q&A
// are reachable from the Capture header.

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

export type OriginalFile = { uri: string; name: string; type: string };

export type RootStackParamList = {
  Capture: undefined;
  Review: { candidate: any; originalFile?: OriginalFile };
  BillDetail: { bill: any };
  Dashboard: undefined;
  QAChat: undefined;
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
      <Text style={{ color: "#2563eb", fontWeight: "600", fontSize: 15 }}>{label}</Text>
    </Pressable>
  );
}

export function RootNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Capture">
        <Stack.Screen
          name="Capture"
          component={CaptureScreen}
          options={({ navigation }) => ({
            title: "Billology",
            headerRight: () => (
              <View style={{ flexDirection: "row", gap: 16 }}>
                <HeaderLink label="Spending" onPress={() => navigation.navigate("Dashboard")} />
                <HeaderLink label="Ask" onPress={() => navigation.navigate("QAChat")} />
              </View>
            ),
          })}
        />
        <Stack.Screen name="Review" component={ReviewRoute} options={{ title: "Review & save" }} />
        <Stack.Screen name="BillDetail" component={BillDetailRoute} options={{ title: "Bill" }} />
        <Stack.Screen name="Dashboard" component={DashboardScreen} options={{ title: "Spending" }} />
        <Stack.Screen name="QAChat" component={QAChatScreen} options={{ title: "Ask" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
