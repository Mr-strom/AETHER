import { COOKIE_NAME } from "../shared/const.js";
import { z } from "zod";
import { getSessionCookieOptions } from "./_core/cookies";
import { invokeLLM, listLLMModels } from "./_core/llm";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";

const explanationInput = z.object({
  question: z.string().trim().min(1).max(600),
  evidenceId: z.string().trim().min(1).max(80),
  sourceName: z.string().trim().min(1).max(180),
  snippet: z.string().trim().min(1).max(5000),
  matchedTerms: z.array(z.string().trim().min(1).max(80)).max(20),
});

export function buildOnlineEvidencePrompt(input: z.infer<typeof explanationInput>) {
  return `Question:\n${input.question}\n\nSelected evidence [${input.evidenceId}] from ${input.sourceName}:\n${input.snippet}\n\nLocal retrieval terms: ${input.matchedTerms.join(", ") || "none"}`;
}

export function extractExplanationText(content: string | Array<{ type: "text"; text: string } | { type: "image_url" } | { type: "file_url" }> | undefined): string | undefined {
  if (typeof content === "string") return content.trim() || undefined;
  const text = content?.flatMap((part) => part.type === "text" ? [part.text] : []).join("\n").trim();
  return text || undefined;
}

export const appRouter = router({
  // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query((opts) => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),

  explainEvidence: publicProcedure.input(explanationInput).mutation(async ({ input }) => {
    const catalog = await listLLMModels().catch(() => ({ data: [] }));
    const model = catalog.data.find((candidate) => candidate.id === "gpt-5-mini")?.id
      ?? catalog.data.find((candidate) => candidate.id.includes("mini") || candidate.id.includes("flash"))?.id;
    const response = await invokeLLM({
      model,
      maxTokens: 650,
      messages: [
        { role: "system", content: "You explain why a local evidence snippet was retrieved. Be concise, factual, and grounded only in the supplied question and snippet. State what the snippet directly supports, what it does not establish, and how the listed matching terms relate. Do not invent missing facts, do not give hidden reasoning, and do not claim to have read any other document." },
        { role: "user", content: buildOnlineEvidencePrompt(input) },
      ],
    });
    const explanation = extractExplanationText(response.choices?.[0]?.message?.content);
    if (!explanation) throw new Error("The online explanation service returned no usable explanation.");
    return { explanation, model: response.model ?? model ?? "managed service" };
  }),

  // TODO: add feature routers here, e.g.
  // todo: router({
  //   list: protectedProcedure.query(({ ctx }) =>
  //     db.getUserTodos(ctx.user.id)
  //   ),
  // }),
});

export type AppRouter = typeof appRouter;
