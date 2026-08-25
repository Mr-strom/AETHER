import { describe, expect, it } from "vitest";

import { buildOnlineEvidencePrompt, extractExplanationText } from "../server/routers";

describe("online evidence explanation boundary", () => {
  it("limits the LLM context to the selected question and snippet", () => {
    const prompt = buildOnlineEvidencePrompt({
      question: "Why was this selected?",
      evidenceId: "EID-7",
      sourceName: "policy.txt",
      snippet: "Citation validation maps every answer citation to selected evidence.",
      matchedTerms: ["citation", "validation"],
    });
    expect(prompt).toContain("Why was this selected?");
    expect(prompt).toContain("EID-7");
    expect(prompt).toContain("Citation validation");
    expect(prompt).not.toContain("entire library");
  });

  it("accepts both plain-text and text-part model responses", () => {
    expect(extractExplanationText("  Grounded explanation.  ")).toBe("Grounded explanation.");
    expect(extractExplanationText([{ type: "text", text: "First point." }, { type: "text", text: "Second point." }])).toBe("First point.\nSecond point.");
    expect(extractExplanationText([{ type: "image_url" }])).toBeUndefined();
  });
});
