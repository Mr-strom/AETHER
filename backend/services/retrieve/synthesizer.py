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
    "You are an evidence synthesizer. You have access ONLY to the evidence units provided.\n"
    "Rules:\n"
    "1) Every factual claim MUST cite one or more evidence IDs in brackets [EID-xxx].\n"
    "2) If evidence is insufficient, return exactly: INSUFFICIENT_EVIDENCE.\n"
    "3) Do not use outside knowledge.\n"
    "4) End with 'Unknowns:' section listing missing evidence."
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
    ) -> SynthesisResult:
        """Synthesize answer using Qwen2.5-3B model.

        Args:
            evidence: List of RetrievalResult objects from hybrid retriever.
            query: Raw user query string.

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

        # Build evidence context block
        context_blocks = []
        for item in evidence:
            eid = item.evidence_id
            page_str = f", Page: {item.page_number}" if item.page_number is not None else ""
            block = f"[{eid}] Source: {item.source_name}{page_str}\n{item.text}"
            context_blocks.append(block)

        evidence_context = "\n\n".join(context_blocks)
        user_prompt = f"EVIDENCE:\n{evidence_context}\n\nQUESTION: {query}"

        logger.info("Synthesizing answer for query '%s' with %d evidence items...", query, len(evidence))

        try:
            qwen = model_manager.get("qwen")
            messages = [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            response = qwen.create_chat_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=512,
            )

            raw_answer = response["choices"][0]["message"]["content"].strip()
            logger.debug("Raw synthesizer output:\n%s", raw_answer)

            # Extract cited [EID-xxx] tags
            cited_ids = self._extract_cited_ids(raw_answer)

            # Determine confidence level
            confidence = "high"
            if "INSUFFICIENT_EVIDENCE" in raw_answer:
                confidence = "low"
            elif not cited_ids:
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
            # Unload qwen after synthesis to keep RAM usage low per Smart Model Manager policy
            model_manager.unload("qwen")

    def _extract_cited_ids(self, text: str) -> List[str]:
        """Extract unique EID citations like [EID-123] or [EID-1] from text."""
        matches = re.findall(r"\[(EID-\w+)\]", text, re.IGNORECASE)
        unique_ids: Set[str] = set()
        for match in matches:
            unique_ids.add(match.upper())
        return sorted(list(unique_ids))


answer_synthesizer_service = AnswerSynthesizerService()
