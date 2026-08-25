import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { Tabs } from "expo-router";
import { Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const bottomPadding = Platform.OS === "web" ? 10 : Math.max(insets.bottom, 8);
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: "#5B5BD6", tabBarInactiveTintColor: "#858994", tabBarStyle: { height: 59 + bottomPadding, paddingTop: 8, paddingBottom: bottomPadding, borderTopColor: "#E7E7E3", backgroundColor: "#FFFFFF" }, tabBarLabelStyle: { fontSize: 11, fontWeight: "700" } }}><Tabs.Screen name="index" options={{ title: "Chat", tabBarIcon: ({ color }) => <MaterialIcons name="chat-bubble-outline" size={22} color={color} /> }} /><Tabs.Screen name="sources" options={{ title: "Sources", tabBarIcon: ({ color }) => <MaterialIcons name="folder-open" size={22} color={color} /> }} /><Tabs.Screen name="settings" options={{ title: "Settings", tabBarIcon: ({ color }) => <MaterialIcons name="settings" size={22} color={color} /> }} /></Tabs>;
}
