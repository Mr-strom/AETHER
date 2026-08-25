import { describe, expect, it } from "vitest";

import { buildExtractiveAnswer, chunkText, retrieveLocalEvidence, validateCitations } from "../lib/aether/engine";
import { MAX_AUDIO_IMPORT_BYTES, MAX_IMPORT_BYTES, validateAudioImportCandidate, validateImportCandidate, validateLocalQuery, validateTextContent } from "../lib/aether/import-validation";
import { EvidenceChunk, createEmptySnapshot } from "../lib/aether/types";

const chunk = (id: string, text: string): EvidenceChunk => ({
  id,
  evidenceId: id,
  sourceId: "source-1",
  sourceName: "policy.txt",
  chunkIndex: 0,
  text,
  createdAt: "2026-08-25T00:00:00.000Z",
});

describe("AETHER local evidence engine", () => {
  it("chunks long text without returning empty items", () => {
    const input = `${"Offline evidence systems keep source metadata. ".repeat(80)}\n\n${"Citation validation prevents unsupported claims. ".repeat(80)}`;
    const output = chunkText(input, 600, 80);
    expect(output.length).toBeGreaterThan(2);
    expect(output.every((value) => value.trim().length > 0)).toBe(true);
  });

  it("retrieves evidence using local query terms", () => {
    const results = retrieveLocalEvidence("How does citation validation work?", [
      chunk("EID-1", "Citation validation checks every displayed evidence identifier before an answer is shown."),
      chunk("EID-2", "A device can store a document locally without a cloud account."),
    ]);
    expect(results[0].evidenceId).toBe("EID-1");
    expect(results[0].matchedTerms).toContain("citation");
  });

  it("returns a cited extractive answer when evidence is sufficient", () => {
    const hits = retrieveLocalEvidence("citation validation", [chunk("EID-3", "Citation validation maps each answer citation to a selected evidence chunk.")]);
    const result = buildExtractiveAnswer("citation validation", hits, 12);
    expect(result.trace.mode).toBe("extractive");
    expect(result.answer).toContain("[EID-3]");
    expect(validateCitations(result.answer, hits)).toBe(true);
    expect(result.trace.pipeline.map((event) => event.stage)).toEqual(["query", "retrieval", "evidence", "validation"]);
  });

  it("abstains instead of inventing an answer when there is no evidence", () => {
    const result = buildExtractiveAnswer("What is the moon made of?", [], 4);
    expect(result.trace.mode).toBe("abstained");
    expect(result.answer.startsWith("INSUFFICIENT_EVIDENCE")).toBe(true);
  });

  it("rejects citations that were not selected as evidence", () => {
    const hits = retrieveLocalEvidence("local", [chunk("EID-4", "This content stays local to the device.")]);
    expect(validateCitations("This is local [EID-made-up]", hits)).toBe(false);
  });

  it("accepts only supported text-document imports", () => {
    expect(() => validateImportCandidate("notes.md", 410)).not.toThrow();
    expect(() => validateImportCandidate("policy.txt", 410)).not.toThrow();
    expect(() => validateImportCandidate("slides.pdf", 410)).toThrow("Choose TXT");
    expect(() => validateImportCandidate("archive.docx", 410)).toThrow("Choose TXT");
  });

  it("gives deterministic recovery errors for empty and oversized imports", () => {
    expect(() => validateImportCandidate("empty.txt", 0)).toThrow("empty");
    expect(() => validateImportCandidate("large.txt", MAX_IMPORT_BYTES + 1)).toThrow("12 MB");
  });

  it("rejects binary-like text and unsafe direct-call queries", () => {
    expect(() => validateTextContent("safe\u0000binary")).toThrow("binary");
    expect(() => validateLocalQuery("a".repeat(601))).toThrow("600 characters");
    expect(() => validateLocalQuery("status\u0007")).toThrow("control characters");
    expect(validateLocalQuery("  Show local citations  ")).toBe("Show local citations");
  });

  it("keeps a timestamped audio segment retrievable as normal local evidence", () => {
    const audio: EvidenceChunk = { ...chunk("EID-audio-1", "The operator reported corrosion on the north pipe."), modality: "audio", startMs: 84_000, endMs: 105_000 };
    const results = retrieveLocalEvidence("operator corrosion", [audio]);
    expect(results[0].modality).toBe("audio");
    expect(results[0].startMs).toBe(84_000);
    expect(results[0].endMs).toBe(105_000);
  });

  it("accepts only safe WAV audio evidence imports", () => {
    expect(() => validateAudioImportCandidate("field-report.wav", 1024)).not.toThrow();
    expect(() => validateAudioImportCandidate("field-report.mp3", 1024)).toThrow("WAV");
    expect(() => validateAudioImportCandidate("empty.wav", 0)).toThrow("empty");
    expect(() => validateAudioImportCandidate("too-large.wav", MAX_AUDIO_IMPORT_BYTES + 1)).toThrow("120 MB");
  });

  it("normalizes a local audio-evidence query before it is sent", () => {
    expect(validateLocalQuery("  Explain citation validation from my file  ")).toBe("Explain citation validation from my file");
  });

  it("starts with an honest resource-telemetry fallback until Android reports native metrics", () => {
    const snapshot = createEmptySnapshot();
    expect(snapshot.telemetry.nativeAvailable).toBe(false);
    expect(snapshot.telemetry.freeMemoryMB).toBeUndefined();
    expect(snapshot.telemetry.note).toContain("RAM");
  });
});
