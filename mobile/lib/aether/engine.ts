import { ChatMessage, ConversationExchange, EvidenceChunk, ExplainabilityTrace, RetrievalHit } from "./types";

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

export function calculateTextOverlap(textA: string, textB: string): number {
  const normA = normalizeText(textA).toLowerCase();
  const normB = normalizeText(textB).toLowerCase();
  if (!normA || !normB) return 0;
  if (normA === normB) return 1.0;

  const tokensA = tokenize(normA);
  const tokensB = tokenize(normB);
  if (!tokensA.length || !tokensB.length) return 0;

  const setA = new Set(tokensA);
  const setB = new Set(tokensB);
  let intersection = 0;
  for (const token of setA) {
    if (setB.has(token)) intersection++;
  }

  const minSize = Math.min(setA.size, setB.size);
  if (minSize === 0) return 0;

  const containment = intersection / minSize;
  const unionSize = setA.size + setB.size - intersection;
  const jaccard = unionSize > 0 ? intersection / unionSize : 0;
  return Math.max(jaccard, containment);
}

export function deduplicateHits(
  hits: RetrievalHit[],
  overlapThreshold = 0.8,
  maxChunks = 5,
): RetrievalHit[] {
  const sorted = [...hits].sort((left, right) => right.score - left.score);
  const selected: RetrievalHit[] = [];

  for (const candidate of sorted) {
    if (selected.length >= maxChunks) break;

    const isDuplicate = selected.some((accepted) => {
      const overlap = calculateTextOverlap(candidate.text, accepted.text);
      return overlap > overlapThreshold;
    });

    if (!isDuplicate) {
      selected.push(candidate);
    }
  }

  return selected;
}

export function getRecentExchanges(messages: ChatMessage[], maxExchanges = 3): ConversationExchange[] {
  const exchanges: ConversationExchange[] = [];
  let pendingUser: string | undefined;

  for (const msg of messages) {
    if (msg.role === "user") {
      pendingUser = msg.text;
    } else if (msg.role === "assistant" && pendingUser !== undefined) {
      exchanges.push({ user: pendingUser, assistant: msg.text });
      pendingUser = undefined;
    }
  }

  return exchanges.slice(-maxExchanges);
}

export function checkRecentRepetition(
  candidateText: string,
  recentExchanges: ConversationExchange[],
  threshold = 0.6,
): { isRepeated: boolean; matchedExchange?: ConversationExchange; overlap: number } {
  if (!candidateText || !recentExchanges.length) {
    return { isRepeated: false, overlap: 0 };
  }

  const cleanCandidate = candidateText.replace(/\[EID-[^\]]+\]/g, "").trim();
  if (!cleanCandidate) return { isRepeated: false, overlap: 0 };

  for (let i = recentExchanges.length - 1; i >= 0; i--) {
    const exchange = recentExchanges[i];
    const cleanPast = exchange.assistant.replace(/\[EID-[^\]]+\]/g, "").trim();
    const overlap = calculateTextOverlap(cleanCandidate, cleanPast);
    if (overlap >= threshold) {
      return { isRepeated: true, matchedExchange: exchange, overlap };
    }
  }

  return { isRepeated: false, overlap: 0 };
}

export function applyAntiRepetitionGuard(
  answer: string,
  hits: RetrievalHit[],
  recentExchanges: ConversationExchange[] = [],
): string {
  if (!recentExchanges.length || !answer || answer.startsWith("INSUFFICIENT_EVIDENCE")) {
    return answer;
  }

  const lower = answer.toLowerCase().trim();
  if (lower.startsWith("as i mentioned earlier") || lower.startsWith("as mentioned earlier")) {
    return answer;
  }

  const repCheck = checkRecentRepetition(answer, recentExchanges, 0.6);
  if (!repCheck.isRepeated) {
    return answer;
  }

  const pastAssistantTexts = recentExchanges.map((ex) => ex.assistant.replace(/\[EID-[^\]]+\]/g, "").trim());
  const freshHit = hits.find((hit) => {
    const cleanHit = hit.text.replace(/\[EID-[^\]]+\]/g, "").trim();
    return !pastAssistantTexts.some((past) => calculateTextOverlap(cleanHit, past) >= 0.5);
  });

  const citations = answer.match(/\[EID-[^\]]+\]/g) ?? [];
  const citationSuffix = citations.length ? ` ${citations[0]}` : "";
  const baseAnswerClean = answer.replace(/\[EID-[^\]]+\]/g, "").trim();

  if (freshHit) {
    const freshSnippet = freshHit.text.length > 320 ? `${freshHit.text.slice(0, 320).trimEnd()}…` : freshHit.text;
    return `As I mentioned earlier, ${baseAnswerClean}${citationSuffix}. In addition, ${freshSnippet} [${freshHit.evidenceId}]`;
  }

  return `As I mentioned earlier, ${baseAnswerClean}${citationSuffix}`;
}

export function retrieveLocalEvidence(query: string, chunks: EvidenceChunk[], limit = 5): RetrievalHit[] {
  const queryTerms = tokenize(query);
  if (!queryTerms.length || !chunks.length) return [];

  const scored = chunks
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
    .sort((left, right) => right.score - left.score);

  return deduplicateHits(scored, 0.8, Math.min(limit, 5));
}

export function buildExtractiveAnswer(
  query: string,
  hits: RetrievalHit[],
  latencyMs: number,
  recentExchanges: ConversationExchange[] = [],
): { answer: string; trace: ExplainabilityTrace } {
  const dedupedHits = deduplicateHits(hits, 0.8, 5);
  const queryTerms = tokenize(query);
  const citations = dedupedHits.map((hit) => `[${hit.evidenceId}]`);
  const candidateCount = dedupedHits.length;
  const best = dedupedHits[0];

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
        hits: dedupedHits,
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
  const supportingLine = dedupedHits.length > 1 ? `\n\nAdditional supporting evidence: ${citations.slice(1).join(" ")}` : "";

  const initialAnswer = `${conciseSnippet} ${citations[0]}${supportingLine}`;
  const finalAnswer = applyAntiRepetitionGuard(initialAnswer, dedupedHits, recentExchanges);

  return {
    answer: finalAnswer,
    trace: {
      mode: "extractive",
      query,
      queryTerms,
      retrievalMethod: "Local lexical retrieval over indexed document chunks",
      candidateCount,
      selectedEvidenceIds: dedupedHits.map((hit) => hit.evidenceId),
      citationsValid: true,
      confidence,
      latencyMs,
      runtimeNote: "Extractive evidence mode is active. The answer uses local source text directly.",
      hits: dedupedHits,
      pipeline: [
        { stage: "query", title: "Validated question", detail: `${queryTerms.length} meaningful query term${queryTerms.length === 1 ? "" : "s"} extracted locally.`, durationMs: 0, status: "complete" },
        { stage: "retrieval", title: "Searched local evidence", detail: `${candidateCount} selected evidence chunk${candidateCount === 1 ? "" : "s"} ranked from the local index.`, durationMs: latencyMs, status: "complete" },
        { stage: "evidence", title: "Prepared cited evidence", detail: `Selected ${dedupedHits.map((hit) => hit.evidenceId).join(", ")} for the grounded answer.`, durationMs: 0, status: "complete" },
        { stage: "validation", title: "Validated evidence references", detail: "Extractive mode references only selected local evidence.", durationMs: 0, status: "complete" },
      ],
    },
  };
}

export const AETHER_SYSTEM_PROMPT = `You are AETHER, an offline document intelligence system. 
Rules:
1. Answer in 3-5 sentences maximum unless the user asks for detail.
2. NEVER repeat information already given in the conversation.
3. ALWAYS cite sources using [EID-XXX] format as clickable pills.
4. If evidence is insufficient, say 'INSUFFICIENT_EVIDENCE' in one sentence.
5. Use natural conversational tone. Do NOT use numbered lists unless user asks for steps.
6. Never suggest 'test questions' or 'key facts' sections unless asked.`;

export function buildGroundedPrompt(
  query: string,
  hits: RetrievalHit[],
  recentExchanges: ConversationExchange[] = [],
  maxChunks = 5,
): string {
  const dedupedHits = deduplicateHits(hits, 0.8, maxChunks);
  const evidence = dedupedHits
    .map((hit) => `[${hit.evidenceId}] Source: ${hit.sourceName}\n${hit.text}`)
    .join("\n\n---\n\n");

  const historySection = recentExchanges.length
    ? `\n\nRecent Conversation History (last ${recentExchanges.length} turns):\n` +
      recentExchanges
        .map((ex) => `User: ${ex.user}\nAssistant: ${ex.assistant}`)
        .join("\n\n")
    : "";

  return `${AETHER_SYSTEM_PROMPT}${historySection}\n\nEvidence:\n${evidence}\n\nQuestion: ${query}`;
}

export function validateCitations(answer: string, hits: RetrievalHit[]): boolean {
  const allowed = new Set(hits.map((hit) => hit.evidenceId));
  const citations = answer.match(/\[EID-[^\]]+\]/g) ?? [];
  if (answer.startsWith("INSUFFICIENT_EVIDENCE")) return citations.length === 0;
  return citations.length > 0 && citations.every((citation) => allowed.has(citation.slice(1, -1)));
}
