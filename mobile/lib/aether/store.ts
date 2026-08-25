import AsyncStorage from "@react-native-async-storage/async-storage";

import { AetherSnapshot, createEmptySnapshot } from "./types";

const STORE_KEY = "@aether-offline/mobile-snapshot-v1";

export async function loadSnapshot(): Promise<AetherSnapshot> {
  const raw = await AsyncStorage.getItem(STORE_KEY);
  if (!raw) return createEmptySnapshot();
  try {
    const parsed = JSON.parse(raw) as Partial<AetherSnapshot>;
    return {
      ...createEmptySnapshot(), ...parsed,
      runtime: { ...createEmptySnapshot().runtime, ...parsed.runtime, loaded: false, loading: false },
      audioModel: { ...createEmptySnapshot().audioModel, ...parsed.audioModel, loading: false },
      telemetry: { ...createEmptySnapshot().telemetry, ...parsed.telemetry },
    };
  } catch { return createEmptySnapshot(); }
}

export async function saveSnapshot(snapshot: AetherSnapshot): Promise<void> {
  const safeSnapshot: AetherSnapshot = { ...snapshot, runtime: { ...snapshot.runtime, loaded: false, loading: false }, audioModel: { ...snapshot.audioModel, loading: false } };
  await AsyncStorage.setItem(STORE_KEY, JSON.stringify(safeSnapshot));
}

export async function clearSnapshot(): Promise<void> { await AsyncStorage.removeItem(STORE_KEY); }
