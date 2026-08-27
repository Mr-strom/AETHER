import { describe, expect, it } from "vitest";

import { AETHER_SYSTEM_PROMPT, applyAntiRepetitionGuard, buildExtractiveAnswer, buildGroundedPrompt, calculateTextOverlap, checkRecentRepetition, chunkText, convertListsToNaturalSentences, deduplicateHits, getRecentExchanges, retrieveLocalEvidence, validateCitations } from "../lib/aether/engine";
import { MAX_AUDIO_IMPORT_BYTES, MAX_IMPORT_BYTES, validateAudioImportCandidate, validateImportCandidate, validateLocalQuery, validateTextContent } from "../lib/aether/import-validation";
import { ChatMessage, ConversationExchange, EvidenceChunk, createEmptySnapshot } from "../lib/aether/types";

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

  it("builds grounded prompt with updated system prompt and formatted evidence", () => {
    const hits = retrieveLocalEvidence("citation validation", [
      chunk("EID-3", "Citation validation maps each answer citation to a selected evidence chunk."),
    ]);
    const prompt = buildGroundedPrompt("How does validation work?", hits);
    expect(prompt).toContain(AETHER_SYSTEM_PROMPT);
    expect(prompt).toContain("You are AETHER, an offline document intelligence system.");
    expect(prompt).toContain("Rules:\n1. Answer in 3-5 sentences maximum");
    expect(prompt).toContain("[EID-3] Source: policy.txt");
    expect(prompt).toContain("Question: How does validation work?");
  });

  it("calculates text overlap correctly between near-identical and distinct texts", () => {
    const textA = "The voltage rating on circuit board A is 120V with high efficiency.";
    const textB = "The voltage rating on circuit board A is 120V with high efficiency and low heat.";
    const textC = "Operating temperature must remain below 45 degrees Celsius.";
    
    expect(calculateTextOverlap(textA, textB)).toBeGreaterThan(0.8);
    expect(calculateTextOverlap(textA, textC)).toBeLessThan(0.3);
  });

  it("deduplicates chunks with >80% overlap, keeping only the higher-scored chunk", () => {
    const highScoredDup = {
      ...chunk("EID-high", "AETHER provides offline document intelligence and citation verification for local files."),
      matchedTerms: ["offline", "document"],
      lexicalScore: 0.95,
      score: 0.95,
    };
    const lowScoredDup = {
      ...chunk("EID-low", "AETHER provides offline document intelligence and citation verification for local files with extra details."),
      matchedTerms: ["offline", "document"],
      lexicalScore: 0.75,
      score: 0.75,
    };
    const uniqueChunk = {
      ...chunk("EID-unique", "Thermal threshold of the hardware must not exceed 85 degrees Celsius."),
      matchedTerms: ["hardware"],
      lexicalScore: 0.60,
      score: 0.60,
    };

    const deduped = deduplicateHits([lowScoredDup, highScoredDup, uniqueChunk], 0.8, 5);
    expect(deduped).toHaveLength(2);
    expect(deduped[0].evidenceId).toBe("EID-high");
    expect(deduped[1].evidenceId).toBe("EID-unique");
    expect(deduped.some((h) => h.evidenceId === "EID-low")).toBe(false);
  });

  it("enforces max chunks sent to LLM at 5 (not 10, not 20)", () => {
    const sampleTopics = [
      "Thermal cooling systems maintain device core below critical threshold.",
      "Battery auxiliary power units provide uninterrupted operations during blackout.",
      "Memory allocation strategies optimize garbage collection on constrained nodes.",
      "Secure cryptographic key exchanges ensure encrypted transport protocols.",
      "Asynchronous message dispatch queues prevent UI main thread stalls.",
      "Local vector similarity indices accelerate nearest neighbor lookups.",
      "Persistent storage caching reduces disk I/O latency on flash drives.",
      "Network packet compression decreases bandwidth usage over air-gapped channels.",
      "Dynamic load balancing distributes parallel worker execution evenly.",
      "Hardware abstraction layers isolate platform specific peripheral drivers.",
      "Database journal write-ahead logging guarantees atomic transaction safety.",
      "Input sanitation routines filter control characters and prevent injection.",
      "Diagnostic trace telemetry captures pipeline execution durations.",
      "Citation verification algorithms validate reference IDs against evidence sets.",
      "Resource telemetry monitors native heap allocations and system limits.",
    ];

    const manyChunks = Array.from({ length: 15 }, (_, i) => ({
      ...chunk(`EID-${i + 1}`, sampleTopics[i]),
      matchedTerms: [`topic ${i + 1}`],
      lexicalScore: 0.9 - i * 0.02,
      score: 0.9 - i * 0.02,
    }));

    const deduped = deduplicateHits(manyChunks, 0.8, 5);
    expect(deduped).toHaveLength(5);
    expect(deduped.map((h) => h.evidenceId)).toEqual(["EID-1", "EID-2", "EID-3", "EID-4", "EID-5"]);

    const prompt = buildGroundedPrompt("query", manyChunks);
    const citedChunksInPrompt = prompt.match(/\[EID-\d+\]/g) ?? [];
    expect(citedChunksInPrompt).toHaveLength(5);
  });

  it("stores and extracts the last 3 user-assistant exchanges from message history", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "user", text: "Q1", createdAt: "", citations: [] },
      { id: "2", role: "assistant", text: "A1 [EID-1]", createdAt: "", citations: ["EID-1"] },
      { id: "3", role: "user", text: "Q2", createdAt: "", citations: [] },
      { id: "4", role: "assistant", text: "A2 [EID-2]", createdAt: "", citations: ["EID-2"] },
      { id: "5", role: "user", text: "Q3", createdAt: "", citations: [] },
      { id: "6", role: "assistant", text: "A3 [EID-3]", createdAt: "", citations: ["EID-3"] },
      { id: "7", role: "user", text: "Q4", createdAt: "", citations: [] },
      { id: "8", role: "assistant", text: "A4 [EID-4]", createdAt: "", citations: ["EID-4"] },
    ];

    const exchanges = getRecentExchanges(messages, 3);
    expect(exchanges).toHaveLength(3);
    expect(exchanges[0]).toEqual({ user: "Q2", assistant: "A2 [EID-2]" });
    expect(exchanges[1]).toEqual({ user: "Q3", assistant: "A3 [EID-3]" });
    expect(exchanges[2]).toEqual({ user: "Q4", assistant: "A4 [EID-4]" });
  });

  it("detects when an answer repeats information said in the last 3 turns", () => {
    const recentExchanges: ConversationExchange[] = [
      { user: "What is the voltage?", assistant: "The operating voltage is 120V with high efficiency [EID-1]." },
    ];

    const repeated = "The operating voltage is 120V with high efficiency [EID-1].";
    const novel = "The thermal cooling system maintains temperature below 35C [EID-2].";

    expect(checkRecentRepetition(repeated, recentExchanges).isRepeated).toBe(true);
    expect(checkRecentRepetition(novel, recentExchanges).isRepeated).toBe(false);
  });

  it("refuses to repeat verbatim and prepends 'As I mentioned earlier...' or pivots to new info", () => {
    const recentExchanges: ConversationExchange[] = [
      { user: "What is the voltage?", assistant: "The operating voltage is 120V with high efficiency [EID-1]." },
    ];

    const candidateAnswer = "The operating voltage is 120V with high efficiency [EID-1].";
    
    // Case 1: No new fresh hits available -> acknowledges earlier mention
    const onlyOldHits = [
      { ...chunk("EID-1", "The operating voltage is 120V with high efficiency."), score: 0.9, lexicalScore: 0.9, matchedTerms: ["voltage"] },
    ];
    const guarded = applyAntiRepetitionGuard(candidateAnswer, onlyOldHits, recentExchanges);
    expect(guarded.startsWith("As I mentioned earlier,")).toBe(true);
    expect(guarded).toContain("120V");
    expect(guarded).toContain("[EID-1]");

    // Case 2: Fresh unmentioned hit available -> pivots to new info
    const hitsWithFresh = [
      { ...chunk("EID-1", "The operating voltage is 120V with high efficiency."), score: 0.9, lexicalScore: 0.9, matchedTerms: ["voltage"] },
      { ...chunk("EID-2", "Battery backup provides 4 hours of auxiliary power during outages."), score: 0.8, lexicalScore: 0.8, matchedTerms: ["power"] },
    ];
    const pivoted = applyAntiRepetitionGuard(candidateAnswer, hitsWithFresh, recentExchanges);
    expect(pivoted.startsWith("As I mentioned earlier,")).toBe(true);
    expect(pivoted).toContain("In addition, Battery backup provides 4 hours of auxiliary power");
    expect(pivoted).toContain("[EID-2]");
  });

  it("includes recent conversation history in the grounded prompt for LLM memory", () => {
    const recentExchanges: ConversationExchange[] = [
      { user: "What is the primary material?", assistant: "The primary material is titanium alloy [EID-1]." },
    ];
    const hits = retrieveLocalEvidence("material", [chunk("EID-1", "The primary material is titanium alloy.")]);
    const prompt = buildGroundedPrompt("What is the material?", hits, recentExchanges);
    expect(prompt).toContain("Recent Conversation History (last 1 turns):");
    expect(prompt).toContain("User: What is the primary material?");
    expect(prompt).toContain("Assistant: The primary material is titanium alloy [EID-1].");
  });

  it("converts numbered and bullet lists into 2-3 natural sentences while preserving citations", () => {
    const listText = "Operational checklist:\n1. Verify circuit integrity [EID-1].\n2. Calibrate sensor inputs [EID-2].\n3. Engage emergency stop [EID-3].";
    const natural = convertListsToNaturalSentences(listText);

    expect(natural).not.toMatch(/1\.\s+/);
    expect(natural).not.toMatch(/2\.\s+/);
    expect(natural).not.toMatch(/3\.\s+/);
    expect(natural).toContain("verify circuit integrity [EID-1]");
    expect(natural).toContain("calibrate sensor inputs [EID-2]");
    expect(natural).toContain("engage emergency stop [EID-3]");
    expect(natural.startsWith("Operational checklist: First,")).toBe(true);
  });
});
