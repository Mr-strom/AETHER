import * as Crypto from "expo-crypto";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";
import { Platform } from "react-native";

import { chunkText, normalizeText } from "./engine";
import { friendlyError, validateAudioImportCandidate, validateImportCandidate, validateTextContent } from "./import-validation";
import { EvidenceChunk, LocalSource } from "./types";

export type ImportedDocument = { source: LocalSource; chunks: EvidenceChunk[] };
export type ImportedAudio = { source: LocalSource };
function safeFileName(name: string): string { return name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 96) || "document.txt"; }

async function indexTextDocument(name: string, mimeType: string | undefined, sizeBytes: number | undefined, rawText: string, existingFingerprints: Set<string>, storedUri: string | undefined, notes: string): Promise<ImportedDocument> {
  const text = normalizeText(rawText); validateTextContent(text);
  const fingerprint = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, text);
  if (existingFingerprints.has(fingerprint)) throw new Error("This document is already indexed on this device.");
  const sourceId = Crypto.randomUUID(); const createdAt = new Date().toISOString();
  const chunks = chunkText(text).map((chunk, index): EvidenceChunk => ({ id: Crypto.randomUUID(), evidenceId: `EID-${sourceId.slice(0, 8)}-${index + 1}`, sourceId, sourceName: name, chunkIndex: index, text: chunk, createdAt, modality: "text" }));
  if (!chunks.length) throw new Error("AETHER could not create searchable text chunks from this file.");
  return { source: { id: sourceId, name, mimeType: mimeType ?? "text/plain", sizeBytes: sizeBytes ?? new TextEncoder().encode(text).length, modality: "text", fingerprint, importedAt: createdAt, status: "ready", chunkCount: chunks.length, storedUri, notes }, chunks };
}

export async function pickAndIndexLocalText(existingFingerprints: Set<string>): Promise<ImportedDocument | null> {
  const result = await DocumentPicker.getDocumentAsync({ type: "*/*", copyToCacheDirectory: true });
  if (result.canceled) return null;
  const asset = result.assets?.[0]; if (!asset) throw new Error("No file was returned by the file picker. Please choose the file again."); validateImportCandidate(asset.name, asset.size);
  if (Platform.OS === "web") { const browserFile = asset.file; if (!browserFile) throw new Error("The browser did not provide readable file content. Use Chrome or Edge and select the file again."); return indexTextDocument(asset.name, asset.mimeType, asset.size, await browserFile.text(), existingFingerprints, undefined, "Indexed in browser preview. The original file is not retained by the browser preview."); }
  const sourceId = Crypto.randomUUID(); const baseDirectory = `${FileSystem.documentDirectory}aether-sources/`; const destination = `${baseDirectory}${sourceId}-${safeFileName(asset.name)}`;
  try { const selectedFile = await FileSystem.getInfoAsync(asset.uri); if (!selectedFile.exists) throw new Error("Android could not read this selected file. Choose it from Files or Downloads and try again."); await FileSystem.makeDirectoryAsync(baseDirectory, { intermediates: true }); await FileSystem.copyAsync({ from: asset.uri, to: destination }); const copiedFile = await FileSystem.getInfoAsync(destination); if (!copiedFile.exists || copiedFile.size === 0) throw new Error("The selected file could not be copied into AETHER’s private storage."); return indexTextDocument(asset.name, asset.mimeType, copiedFile.size ?? asset.size, await FileSystem.readAsStringAsync(destination, { encoding: FileSystem.EncodingType.UTF8 }), existingFingerprints, destination, "Copied into AETHER’s private on-device storage and indexed without a cloud upload."); } catch (error) { await FileSystem.deleteAsync(destination, { idempotent: true }).catch(() => undefined); throw new Error(friendlyError(error, "AETHER could not import this file. Choose a supported UTF-8 text file and try again.")); }
}

export async function pickAndStoreLocalAudio(existingFingerprints: Set<string>): Promise<ImportedAudio | null> {
  const result = await DocumentPicker.getDocumentAsync({ type: "audio/wav", copyToCacheDirectory: true });
  if (result.canceled) return null;
  const asset = result.assets?.[0]; if (!asset) throw new Error("No recording was returned by the file picker. Choose a WAV file and try again."); validateAudioImportCandidate(asset.name, asset.size);
  if (Platform.OS === "web") throw new Error("Audio evidence ingestion requires the installed Android app. Browser preview keeps audio private and disabled.");
  const fingerprint = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, `${asset.name}|${asset.size ?? 0}|${asset.mimeType ?? "audio/wav"}`);
  if (existingFingerprints.has(fingerprint)) throw new Error("This recording is already in the local evidence library.");
  const sourceId = Crypto.randomUUID(); const baseDirectory = `${FileSystem.documentDirectory}aether-sources/`; const destination = `${baseDirectory}${sourceId}-${safeFileName(asset.name)}`;
  try { await FileSystem.makeDirectoryAsync(baseDirectory, { intermediates: true }); await FileSystem.copyAsync({ from: asset.uri, to: destination }); const copied = await FileSystem.getInfoAsync(destination); if (!copied.exists || !copied.size) throw new Error("The recording could not be copied into AETHER’s private storage."); return { source: { id: sourceId, name: asset.name, mimeType: asset.mimeType ?? "audio/wav", sizeBytes: copied.size, fingerprint, importedAt: new Date().toISOString(), status: "indexing", chunkCount: 0, modality: "audio", storedUri: destination, notes: "Saved privately on-device. AETHER will transcribe it locally into timestamped evidence segments." } }; } catch (error) { await FileSystem.deleteAsync(destination, { idempotent: true }).catch(() => undefined); throw new Error(friendlyError(error, "AETHER could not store this audio file privately.")); }
}

export async function removeStoredSource(uri?: string): Promise<void> { if (Platform.OS === "web" || !uri) return; const details = await FileSystem.getInfoAsync(uri); if (details.exists) await FileSystem.deleteAsync(uri, { idempotent: true }); }
export async function clearStoredSources(): Promise<void> { if (Platform.OS === "web") return; const directory = `${FileSystem.documentDirectory}aether-sources/`; const details = await FileSystem.getInfoAsync(directory); if (details.exists) await FileSystem.deleteAsync(directory, { idempotent: true }); }
