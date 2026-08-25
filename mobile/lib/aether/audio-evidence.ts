import * as Crypto from "expo-crypto";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";
import { Platform } from "react-native";
import { AudioModelState, EvidenceChunk, LocalSource } from "./types";

const AUDIO_MODEL_ROOT = `${FileSystem.documentDirectory ?? ""}aether-audio-models/`;
const MAX_AUDIO_MODEL_BYTES = 420 * 1024 * 1024;
let activeStop: (() => Promise<void>) | undefined;
type WhisperTranscriptionResult = { result: string; language: string; segments: Array<{ text: string; t0: number; t1: number }>; isAborted: boolean };

function nativeOnly() { if (Platform.OS === "web") throw new Error("Audio evidence transcription requires the installed Android app. Browser preview never downloads or runs a cloud speech model."); }
function safeFileName(name: string) { return name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 96) || "ggml-base.bin"; }

export async function installAudioEvidenceModel(): Promise<AudioModelState> {
  nativeOnly();
  const result = await DocumentPicker.getDocumentAsync({ type: "application/octet-stream", copyToCacheDirectory: true });
  if (result.canceled) throw new Error("Whisper model selection was cancelled.");
  const asset = result.assets?.[0]; if (!asset) throw new Error("Android did not return the Whisper model file.");
  if (!asset.name.toLowerCase().endsWith(".bin")) throw new Error("Choose a local whisper.cpp GGML model ending in .bin, such as ggml-base.bin.");
  if (!asset.name.toLowerCase().includes("base")) throw new Error("AETHER v1.2 supports the multilingual Whisper Base model. Choose ggml-base.bin or a compatible Base quantized GGML file.");
  if (asset.size && asset.size > MAX_AUDIO_MODEL_BYTES) throw new Error("This audio model exceeds AETHER’s 420 MB mobile safety limit.");
  await FileSystem.makeDirectoryAsync(AUDIO_MODEL_ROOT, { intermediates: true });
  const destination = `${AUDIO_MODEL_ROOT}${safeFileName(asset.name)}`;
  await FileSystem.copyAsync({ from: asset.uri, to: destination });
  const stored = await FileSystem.getInfoAsync(destination); if (!stored.exists || !stored.size) throw new Error("The selected Whisper model could not be copied into private storage.");
  return { installed: true, loading: false, modelPath: destination, modelName: asset.name, note: "Whisper Base is stored locally and loaded only while a WAV recording is transcribed into timestamped evidence." };
}

export async function transcribeAudioEvidence(source: LocalSource, model: AudioModelState): Promise<{ chunks: EvidenceChunk[]; durationMs: number; language: string }> {
  nativeOnly();
  if (!source.storedUri) throw new Error("The private recording file is missing. Import the WAV file again.");
  if (!model.installed || !model.modelPath) throw new Error("Install the local Whisper Base model in Settings before indexing audio evidence.");
  const { initWhisper } = await import("whisper.rn/index");
  const startedAt = Date.now(); const context = await initWhisper({ filePath: model.modelPath, useGpu: false });
  try {
    const task = context.transcribe(source.storedUri, { language: "auto", maxThreads: 2, tokenTimestamps: true, maxLen: 0 });
    activeStop = task.stop;
    const result = await task.promise as WhisperTranscriptionResult;
    if (result.isAborted) throw new Error("Audio indexing was stopped before transcription finished.");
    const segments = result.segments.filter((segment: { text: string; t0: number; t1: number }) => segment.text.trim() && segment.t1 > segment.t0);
    if (!segments.length) throw new Error("No timestamped speech segments were detected. Use a 16 kHz mono PCM WAV recording with clear speech.");
    const createdAt = new Date().toISOString();
    const chunks = segments.map((segment: { text: string; t0: number; t1: number }, index: number): EvidenceChunk => ({ id: Crypto.randomUUID(), evidenceId: `EID-${source.id.slice(0, 8)}-${index + 1}`, sourceId: source.id, sourceName: source.name, chunkIndex: index, text: segment.text.trim(), modality: "audio", startMs: Math.max(0, Math.round(segment.t0)), endMs: Math.max(0, Math.round(segment.t1)), createdAt }));
    return { chunks, durationMs: Date.now() - startedAt, language: result.language };
  } finally { activeStop = undefined; await context.release().catch(() => undefined); }
}

export async function stopAudioEvidenceTranscription() { await activeStop?.().catch(() => undefined); }
export async function sampleAudioEvidenceTelemetry(sourceBytes: number, chunkCount: number, lastOperationMs?: number) { return { sampledAt: new Date().toISOString(), nativeAvailable: false, sourceBytes, chunkCount, lastOperationMs, note: Platform.OS === "web" ? "Audio evidence runs only in the Android app; browser preview does not expose native memory telemetry." : "Whisper Base and the local LLM are released between operations. v1.2 does not show an estimated RAM value." }; }
