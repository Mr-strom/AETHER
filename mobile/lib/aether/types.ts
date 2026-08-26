export type SourceStatus = "ready" | "indexing" | "failed" | "no_text";
export type AnswerMode = "extractive" | "local_model" | "abstained";
export type SourceModality = "text" | "audio";
export type PipelineStage = "query" | "retrieval" | "evidence" | "generation" | "validation" | "abstention";

export type EvidenceChunk = {
  id: string;
  evidenceId: string;
  sourceId: string;
  sourceName: string;
  chunkIndex: number;
  text: string;
  pageNumber?: number;
  modality?: SourceModality;
  startMs?: number;
  endMs?: number;
  createdAt: string;
};

export type LocalSource = {
  id: string;
  name: string;
  mimeType: string;
  sizeBytes: number;
  fingerprint: string;
  importedAt: string;
  status: SourceStatus;
  chunkCount: number;
  modality?: SourceModality;
  storedUri?: string;
  notes?: string;
};

export type RetrievalHit = EvidenceChunk & { score: number; lexicalScore: number; matchedTerms: string[] };
export type PipelineEvent = { stage: PipelineStage; title: string; detail: string; durationMs: number; status: "complete" | "skipped" | "fallback" };
export type ExplainabilityTrace = { mode: AnswerMode; query: string; queryTerms: string[]; retrievalMethod: string; candidateCount: number; selectedEvidenceIds: string[]; citationsValid: boolean; confidence: "high" | "medium" | "low"; abstentionReason?: string; latencyMs: number; runtimeNote: string; hits: RetrievalHit[]; pipeline: PipelineEvent[] };
export type ChatMessage = { id: string; role: "user" | "assistant"; text: string; createdAt: string; citations: string[]; trace?: ExplainabilityTrace };
export type ConversationExchange = { user: string; assistant: string };
export type RuntimeProfile = "lite" | "standard";
export type RuntimeState = { profile: RuntimeProfile; modelPath?: string; modelName?: string; loaded: boolean; loading: boolean; mode: "extractive" | "local_model"; note: string };
export type AudioModelState = { installed: boolean; loading: boolean; modelPath?: string; modelName?: string; note: string };
export type ResourceTelemetry = { sampledAt?: string; nativeAvailable: boolean; freeMemoryMB?: number; usedMemoryMB?: number; systemAvailableMemoryMB?: number; cpuCores?: number; sourceBytes: number; chunkCount: number; lastOperationMs?: number; note: string };
export type AetherSnapshot = { sources: LocalSource[]; chunks: EvidenceChunk[]; messages: ChatMessage[]; runtime: RuntimeState; audioModel: AudioModelState; telemetry: ResourceTelemetry; onlineExplainEnabled: boolean; acceptedNoticeAt?: string };

export const createEmptySnapshot = (): AetherSnapshot => ({
  sources: [], chunks: [], messages: [],
  runtime: { profile: "lite", loaded: false, loading: false, mode: "extractive", note: "Extractive evidence mode is active. Import a local GGUF model pack to enable local generation." },
  audioModel: { installed: false, loading: false, note: "Install a local Whisper Base model to transcribe WAV recordings into timestamped private evidence." },
  telemetry: { nativeAvailable: false, sourceBytes: 0, chunkCount: 0, note: "Native RAM data is unavailable in this v1.2 runtime; AETHER does not estimate or invent a memory value." },
  onlineExplainEnabled: false,
});
