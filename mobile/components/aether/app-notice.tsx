import { Pressable, StyleSheet, Text, View } from "react-native";
import MaterialIcons from "@expo/vector-icons/MaterialIcons";

import { useAether } from "@/lib/aether/provider";

export function AppNotice() {
  const { notice, dismissNotice } = useAether();
  if (!notice) return null;
  const isError = notice.tone === "error";
  const isSuccess = notice.tone === "success";
  return <View pointerEvents="box-none" style={styles.layer}><View style={[styles.card, isError ? styles.error : isSuccess ? styles.success : styles.info]}><MaterialIcons name={isError ? "error-outline" : isSuccess ? "check-circle-outline" : "info-outline"} size={21} color={isError ? "#C33D5A" : isSuccess ? "#0F8A83" : "#1B6EF3"} /><View style={styles.copy}><Text style={styles.title}>{notice.title}</Text><Text style={styles.message}>{notice.message}</Text></View><Pressable accessibilityLabel="Dismiss message" onPress={dismissNotice} hitSlop={10}><MaterialIcons name="close" size={20} color="#607089" /></Pressable></View></View>;
}

const styles = StyleSheet.create({
  layer: { position: "absolute", top: 58, left: 12, right: 12, zIndex: 20 },
  card: { flexDirection: "row", gap: 10, padding: 13, borderRadius: 16, borderWidth: 1, shadowColor: "#10233D", shadowOpacity: 0.12, shadowRadius: 13, shadowOffset: { width: 0, height: 6 }, elevation: 5 },
  error: { backgroundColor: "#FFF4F6", borderColor: "#F8C6D1" }, success: { backgroundColor: "#EEFBF8", borderColor: "#B8E8E1" }, info: { backgroundColor: "#F0F6FF", borderColor: "#C9DDFC" },
  copy: { flex: 1 }, title: { color: "#10233D", fontSize: 13, lineHeight: 17, fontWeight: "800" }, message: { marginTop: 2, color: "#496078", fontSize: 12, lineHeight: 17 },
});
