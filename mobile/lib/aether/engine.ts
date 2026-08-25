import { EvidenceChunk, ExplainabilityTrace, RetrievalHit } from "./types";

const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "where", "which", "who", "with", "why", "you", "your",
]);

export function normalizeText(value: string): string {
  return value.replace(/\r\n/g, "\n").replace(/\u0000/g, "").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

export function tokenize(value: string): string[] {
  return Array.from(
    new Set(
      normalizeText(value)
        .toLowerCase()
        .match(/[\p{L}\p{N}][\p{L}\p{N}'-]{1,}/gu)
        ?.filter((token) => !STOP_WORDS.has(token)) ?? [],
    ),
  );
}

export function chunkText(text: string, chunkSize = 1250, overlap = 180): string[] {
  const normalized = normalizeText(text);
  if (!normalized) return [];
  if (normalized.length <= chunkSize) return [normalized];

  const chunks: string[] = [];
  let start = 0;
  while (start < normalized.length) {
    let end = Math.min(start + chunkSize, normalized.length);
    if (end < normalized.length) {
      const boundary = Math.max(
        normalized.lastIndexOf("\n\n", end),
        normalized.lastIndexOf(". ", end),
        normalized.lastIndexOf(" ", end),
      );
      if (boundary > start + Math.floor(chunkSize * 0.55)) end = boundary + 1;
    }
    const chunk = normalized.slice(start, end).trim();
    if (chunk) chunks.push(chunk);
    if (end >= normalized.length) break;
    start = Math.max(end - overlap, start + 1);
  }
  return chunks;
}

export function retrieveLocalEvidence(query: string, chunks: EvidenceChunk[], limit = 3): RetrievalHit[] {
  const queryTerms = tokenize(query);
  if (!queryTerms.length || !chunks.length) return [];

  return chunks
    .map((chunk) => {
      const text = chunk.text.toLowerCase();
      const matchedTerms = queryTerms.filter((term) => text.includes(term));
      const uniqueMatchRatio = matchedTerms.length / queryTerms.length;
      const phraseBonus = text.includes(query.toLowerCase().trim()) ? 0.35 : 0;
      const firstSentenceBonus = matchedTerms.some((term) => text.slice(0, 320).includes(term)) ? 0.08 : 0;
      const lexicalScore = Math.min(1, uniqueMatchRatio + phraseBonus + firstSentenceBonus);
      return { ...chunk, matchedTerms, lexicalScore, score: lexicalScore };
    })
    .filter((hit) => hit.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export function buildExtractiveAnswer(query: string, hits: RetrievalHit[], latencyMs: number): { answer: string; trace: ExplainabilityTrace } {
  const queryTerms = tokenize(query);
  const citations = hits.map((hit) => `[${hit.evidenceId}]`);
  const candidateCount = hits.length;
  const best = hits[0];

  if (!best || best.score < 0.18) {
    return {
      answer: "INSUFFICIENT_EVIDENCE\n\nI could not find enough matching local evidence to answer that safely. Import a relevant document or ask using terms that appear in your sources.",
      trace: {
        mode: "abstained",
        query,
        queryTerms,
        retrievalMethod: "Local lexical retrieval over indexed document chunks",
        candidateCount,
        selectedEvidenceIds: [],
        citationsValid: true,
        confidence: "low",
        abstentionReason: "No retrieved chunk met the minimum grounded-evidence threshold.",
        latencyMs,
        runtimeNote: "The local model was not used because evidence was insufficient.",
        hits,
        pipeline: [
          { stage: "query", title: "Validated question", detail: `${queryTerms.length} meaningful query term${queryTerms.length === 1 ? "" : "s"} extracted locally.`, durationMs: 0, status: "complete" },
          { stage: "retrieval", title: "Searched local evidence", detail: `${candidateCount} candidate chunk${candidateCount === 1 ? "" : "s"} matched the local index.`, durationMs: latencyMs, status: "complete" },
          { stage: "abstention", title: "Protected against unsupported answer", detail: "No candidate passed AETHER’s grounded-evidence threshold.", durationMs: 0, status: "complete" },
        ],
      },
    };
  }

  const conciseSnippet = best.text.length > 680 ? `${best.text.slice(0, 680).trimEnd()}…` : best.text;
  const confidence = best.score >= 0.62 ? "high" : "medium";
  const supportingLine = hits.length > 1 ? `\n\nAdditional supporting evidence: ${citations.slice(1).join(" ")}` : "";

  return {
    answer: `${conciseSnippet} ${citations[0]}${supportingLine}`,
    trace: {
      mode: "extractive",
      query,
      queryTerms,
      retrievalMethod: "Local lexical retrieval over indexed document chunks",
      candidateCount,
      selectedEvidenceIds: hits.map((hit) => hit.evidenceId),
      citationsValid: true,
      confidence,
      latencyMs,
      runtimeNote: "Extractive evidence mode is active. The answer uses local source text directly.",
      hits,
      pipeline: [
        { stage: "query", title: "Validated question", detail: `${queryTerms.length} meaningful query term${queryTerms.length === 1 ? "" : "s"} extracted locally.`, durationMs: 0, status: "complete" },
        { stage: "retrieval", title: "Searched local evidence", detail: `${candidateCount} selected evidence chunk${candidateCount === 1 ? "" : "s"} ranked from the local index.`, durationMs: latencyMs, status: "complete" },
        { stage: "evidence", title: "Prepared cited evidence", detail: `Selected ${hits.map((hit) => hit.evidenceId).join(", ")} for the grounded answer.`, durationMs: 0, status: "complete" },
        { stage: "validation", title: "Validated evidence references", detail: "Extractive mode references only selected local evidence.", durationMs: 0, status: "complete" },
      ],
    },
  };
}

export function buildGroundedPrompt(query: string, hits: RetrievalHit[]): string {
  const evidence = hits
    .map((hit) => `[${hit.evidenceId}] Source: ${hit.sourceName}\n${hit.text}`)
    .join("\n\n---\n\n");

  return `You are AETHER Offline, a private evidence assistant. Answer only from the evidence below. Every factual sentence must contain one or more valid citations exactly in the form [EID-x]. If the evidence is insufficient, answer exactly with INSUFFICIENT_EVIDENCE and a short reason. Do not mention external knowledge. Keep the answer concise.\n\nEvidence:\n${evidence}\n\nQuestion: ${query}`;
}

export function validateCitations(answer: string, hits: RetrievalHit[]): boolean {
  const allowed = new Set(hits.map((hit) => hit.evidenceId));
  const citations = answer.match(/\[EID-[^\]]+\]/g) ?? [];
  if (answer.startsWith("INSUFFICIENT_EVIDENCE")) return citations.length === 0;
  return citations.length > 0 && citations.every((citation) => allowed.has(citation.slice(1, -1)));
}
