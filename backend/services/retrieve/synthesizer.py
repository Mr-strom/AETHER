"""Answer synthesizer service using Qwen2.5-3B with strict grounding contract enforcement."""

from __future__ import annotations

import logging
import re
from typing import List, Set
from pydantic import BaseModel, Field

from backend.services.model_manager import model_manager
from backend.services.retrieve.retriever import RetrievalResult

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = (
    "You are an evidence synthesizer. Your job is to read the provided evidence and write a clear, concise answer to the user's question.\n\n"
    "STRICT RULES:\n"
    "1) Use ONLY the evidence provided below. Do NOT use outside knowledge.\n"
    "2) Write the answer in YOUR OWN WORDS. Do NOT copy-paste the evidence text.\n"
    "3) Every factual claim MUST end with a citation in the format [EID-xxx], where xxx is the exact evidence number from the evidence block.\n"
    "4) Use ONLY the EID numbers shown in the evidence blocks. Do NOT make up EID numbers.\n"
    "5) If the evidence does not contain enough information to answer the question, return exactly: INSUFFICIENT_EVIDENCE\n"
    "6) After your answer, add a section titled 'Unknowns:' listing any information that is missing or unclear.\n"
    "7) Do NOT include the evidence headers (like 'Source: filename') in your answer. Only use [EID-xxx] citations.\n"
    "8) Keep your answer under 200 words."
)

class SynthesisResult(BaseModel):
    """Result payload produced by the answer synthesizer agent."""

    answer_text: str
    cited_ids: List[str] = Field(default_factory=list)
    confidence: str = Field(default="high")

class AnswerSynthesizerService:
    """Synthesizes factual answers grounded strictly in retrieved evidence units."""

    async def synthesize(
        self,
        evidence: List[RetrievalResult],
        query: str,
        unload_after: bool = True,
    ) -> SynthesisResult:
        """Synthesize answer using Qwen2.5-3B model.

        Args:
            evidence: List of RetrievalResult objects from hybrid retriever.
            query: Raw user query string.
            unload_after: If False, keeps Qwen loaded (useful for batch tests).

        Returns:
            SynthesisResult containing generated answer text, cited EIDs, and confidence.
        """
        if not evidence:
            logger.warning("No evidence provided for synthesis. Returning INSUFFICIENT_EVIDENCE.")
            return SynthesisResult(
                answer_text="INSUFFICIENT_EVIDENCE",
                cited_ids=[],
                confidence="low",
            )

        # Build evidence context block with clear formatting
        context_blocks = []
        for item in evidence:
            eid = item.evidence_id
            page_str = f" (Page {item.page_number})" if item.page_number is not None else ""
            block = f"--- Evidence {eid}{page_str} ---\n{item.text}"
            context_blocks.append(block)

        evidence_context = "\n\n".join(context_blocks)
        user_prompt = (
            f"QUESTION: {query}\n\n"
            f"EVIDENCE:\n{evidence_context}\n\n"
            f"INSTRUCTIONS:\n"
            f"- Answer the question using ONLY the evidence above.\n"
            f"- Cite evidence using exactly this format: [EID-xxx] (e.g., [EID-5], [EID-12]).\n"
            f"- Use ONLY the EID numbers from the '--- Evidence EID-xxx ---' headers above.\n"
            f"- If you cannot answer, say: INSUFFICIENT_EVIDENCE\n"
            f"- End with 'Unknowns:' section."
        )

        logger.info("Synthesizing answer for query '%s' with %d evidence items...", query, len(evidence))

        try:
            qwen = model_manager.get("qwen")
            messages = [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            response = qwen.create_chat_completion(
                messages=messages,
                temperature=0.1,  # Lower temp = less hallucination
                max_tokens=512,
            )

            raw_answer = response["choices"][0]["message"]["content"].strip()
            logger.debug("Raw synthesizer output:\n%s", raw_answer)

            # Extract cited [EID-xxx] tags
            cited_ids = self._extract_cited_ids(raw_answer)

            # Determine confidence based on citation validity
            valid_eids = {e.evidence_id.upper() for e in evidence}
            cited_set = set(cited_ids)
            
            if "INSUFFICIENT_EVIDENCE" in raw_answer.upper():
                confidence = "low"
            elif not cited_ids:
                confidence = "medium"
            elif cited_set.issubset(valid_eids):
                confidence = "high"
            else:
                # Has citations but some are invalid/hallucinated
                invalid = cited_set - valid_eids
                logger.warning("Synthesizer cited invalid EIDs: %s", invalid)
                confidence = "medium"

            return SynthesisResult(
                answer_text=raw_answer,
                cited_ids=cited_ids,
                confidence=confidence,
            )

        except Exception as exc:
            logger.error("Synthesizer agent failed: %s. Returning fallback result.", exc)
            return SynthesisResult(
                answer_text="INSUFFICIENT_EVIDENCE",
                cited_ids=[],
                confidence="low",
            )
        finally:
            if unload_after:
                model_manager.unload("qwen")

    def _extract_cited_ids(self, text: str) -> List[str]:
        """Extract unique EID citations like [EID-123] or [EID-1] from text."""
        matches = re.findall(r"\[(EID-\w+)\]", text, re.IGNORECASE)
        unique_ids: Set[str] = set()
        for match in matches:
            unique_ids.add(match.upper())
        return sorted(list(unique_ids))

answer_synthesizer_service = AnswerSynthesizerService()