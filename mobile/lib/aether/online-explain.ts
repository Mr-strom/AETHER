import { createTRPCClient } from "@/lib/trpc";
import { RetrievalHit } from "./types";

const client = createTRPCClient();

export type OnlineEvidenceExplanation = { explanation: string; model: string };

export async function requestOnlineEvidenceExplanation(hit: RetrievalHit, question: string): Promise<OnlineEvidenceExplanation> {
  return client.explainEvidence.mutate({
    question: question.trim() || "Why was this evidence selected?",
    evidenceId: hit.evidenceId,
    sourceName: hit.sourceName,
    snippet: hit.text.slice(0, 5000),
    matchedTerms: hit.matchedTerms.slice(0, 20),
  });
}
