import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { View } from "react-native";

import { AppNotice } from "@/components/aether/app-notice";
import { FirstLaunchGate } from "@/components/aether/first-launch-gate";
import { AetherProvider } from "@/lib/aether/provider";
import { ThemeProvider } from "@/lib/theme-provider";

export default function RootLayout() {
  return (
    <ThemeProvider>
      <AetherProvider>
        <FirstLaunchGate><View style={{ flex: 1 }}><Stack screenOptions={{ headerShown: false }}><Stack.Screen name="(tabs)" /></Stack><AppNotice /><StatusBar style="dark" /></View></FirstLaunchGate>
      </AetherProvider>
    </ThemeProvider>
  );
}
