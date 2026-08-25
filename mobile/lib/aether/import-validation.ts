export const MAX_IMPORT_BYTES = 12 * 1024 * 1024;
export const MAX_AUDIO_IMPORT_BYTES = 120 * 1024 * 1024;
export const SUPPORTED_TEXT_EXTENSIONS = ["txt", "md", "markdown", "log", "csv", "json", "rst"] as const;
export const SUPPORTED_AUDIO_EXTENSIONS = ["wav"] as const;

export function extensionOf(name: string): string { return name.split(".").pop()?.toLowerCase() ?? ""; }
export function validateImportCandidate(name: string, size?: number): void {
  const extension = extensionOf(name);
  if (!SUPPORTED_TEXT_EXTENSIONS.includes(extension as (typeof SUPPORTED_TEXT_EXTENSIONS)[number])) throw new Error("Choose TXT, MD, CSV, JSON, LOG, or RST for text evidence. PDF, DOCX, images, and audio are not supported by this text importer.");
  if (size !== undefined && size <= 0) throw new Error("This file is empty. Choose a text file containing readable content.");
  if (size !== undefined && size > MAX_IMPORT_BYTES) throw new Error("This file is larger than the 12 MB text limit. Split it into smaller text files, then import them one at a time.");
}
export function validateAudioImportCandidate(name: string, size?: number): void {
  if (extensionOf(name) !== "wav") throw new Error("AETHER v1.2 accepts 16 kHz mono PCM WAV audio only. Convert the recording to WAV before importing so timestamped offline transcription remains reliable.");
  if (size !== undefined && size <= 0) throw new Error("This recording is empty. Choose a WAV file containing speech.");
  if (size !== undefined && size > MAX_AUDIO_IMPORT_BYTES) throw new Error("This recording exceeds the 120 MB mobile safety limit. Split or compress it as 16 kHz mono WAV, then import it again.");
}
export function friendlyError(error: unknown, fallback: string): string { return error instanceof Error && error.message.trim() ? error.message : fallback; }
export function validateTextContent(text: string): void {
  if (!text.trim()) throw new Error("No readable text was found. This file may use an unsupported encoding or contain only empty content.");
  if (text.includes("\u0000")) throw new Error("This file appears to be binary, not readable UTF-8 text. Choose a supported text file instead.");
  const controlCount = [...text].filter((character) => { const code = character.charCodeAt(0); return code < 32 && character !== "\n" && character !== "\r" && character !== "\t"; }).length;
  if (controlCount > Math.max(12, text.length * 0.01)) throw new Error("This file contains too many binary control characters to index safely.");
}
export function validateLocalQuery(query: string): string { const trimmed = query.trim(); if (!trimmed) throw new Error("Enter a question before sending it."); if (trimmed.length > 600) throw new Error("Questions are limited to 600 characters on this mobile build."); if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/.test(trimmed)) throw new Error("This question contains unsupported control characters."); return trimmed; }
