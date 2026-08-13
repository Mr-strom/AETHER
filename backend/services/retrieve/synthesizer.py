"""Answer synthesizer service using Qwen2.5-3B with strict grounding contract enforcement."""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Set
from pydantic import BaseModel, Field

from backend.services.model_manager import model_manager
from backend.services.retrieve.retriever import RetrievalResult

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = (
    "You are an evidence synthesizer. Read the evidence and answer the question concisely.\n\n"
    "STRICT RULES:\n"
    "1) Use ONLY the evidence provided. No outside knowledge.\n"
    "2) Write in YOUR OWN WORDS. Do NOT copy-paste evidence text.\n"
    "3) Put citations at the END of each sentence, like: The voltage is 112V [EID-0].\n"
    "4) Use ONLY the EID numbers from the evidence headers. Do NOT make up EIDs.\n"
    "5) If evidence is insufficient, return exactly: INSUFFICIENT_EVIDENCE\n"
    "6) If sources conflict, add a 'Conflicts:' section BEFORE 'Unknowns:' listing each disagreement with both sources cited.\n"
    "7) After your answer, add 'Unknowns:' listing missing info.\n"
    "8) Keep your answer under 100 words."
)

class SynthesisResult(BaseModel):
    """Result payload produced by the answer synthesizer agent."""

    answer_text: str
    cited_ids: List[str] = Field(default_factory=list)
    confidence: str = Field(default="high")
    conflicts_detected: int = Field(default=0)

class AnswerSynthesizerService:
    """Synthesizes factual answers grounded strictly in retrieved evidence units."""

    async def synthesize(
        self,
        evidence: List[RetrievalResult],
        query: str,
        unload_after: bool = True,
        conflicts: Optional[list] = None,
    ) -> SynthesisResult:
        """Synthesize answer using Qwen2.5-3B model.

        Args:
            evidence: List of RetrievalResult objects from hybrid retriever.
            query: Raw user query string.
            unload_after: If False, keeps Qwen loaded (useful for batch tests).
            conflicts: Optional list of Conflict objects from conflict detector.

        Returns:
            SynthesisResult containing generated answer text, cited EIDs, confidence,
            and number of conflicts detected.
        """
        if not evidence:
            logger.warning("No evidence provided for synthesis. Returning INSUFFICIENT_EVIDENCE.")
            return SynthesisResult(
                answer_text="INSUFFICIENT_EVIDENCE",
                cited_ids=[],
                confidence="low",
                conflicts_detected=0,
            )

        # Build evidence context block with clear formatting
        context_blocks = []
        for item in evidence:
            eid = item.evidence_id
            page_str = f" (Page {item.page_number})" if item.page_number is not None else ""
            block = f"--- Evidence {eid}{page_str} ---\n{item.text}"
            context_blocks.append(block)

        evidence_context = "\n\n".join(context_blocks)

        # Build conflicts section if any detected
        conflicts_block = ""
        conflict_count = 0
        if conflicts:
            conflict_count = len(conflicts)
            from backend.services.retrieve.conflict_detector import conflict_detector
            conflicts_block = conflict_detector.format_conflicts_for_prompt(conflicts)

        user_prompt = (
            f"QUESTION: {query}\n\n"
            f"EVIDENCE:\n{evidence_context}\n\n"
        )

        if conflicts_block:
            user_prompt += f"{conflicts_block}\n\n"

        user_prompt += (
            f"INSTRUCTIONS:\n"
            f"- Answer the question using ONLY the evidence above.\n"
            f"- Cite evidence using exactly this format: [EID-xxx] (e.g., [EID-5], [EID-12]).\n"
            f"- Use ONLY the EID numbers from the '--- Evidence EID-xxx ---' headers above.\n"
            f"- If you cannot answer, say: INSUFFICIENT_EVIDENCE\n"
        )

        if conflicts_block:
            user_prompt += (
                f"- Sources DISAGREE on some values. Acknowledge the conflict, cite BOTH sources, "
                f"and add a 'Conflicts:' section listing each disagreement.\n"
            )

        user_prompt += f"- End with 'Unknowns:' section."

        logger.info("Synthesizing answer for query '%s' with %d evidence items...", query, len(evidence))
        if conflict_count:
            logger.info("Conflicts injected into prompt: %d", conflict_count)

        try:
            qwen = model_manager.get("qwen")
            messages = [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            response = qwen.create_chat_completion(
                messages=messages,
                temperature=0.1,  # Lower temp = less hallucination
                max_tokens=128,
            )

            raw_answer = response["choices"][0]["message"]["content"].strip()
            logger.debug("Raw synthesizer output:\n%s", raw_answer)

            # Extract cited [EID-xxx] tags
            cited_ids = self._extract_cited_ids(raw_answer)

            # Determine confidence based on citation validity and conflicts
            valid_eids = {e.evidence_id.upper() for e in evidence}
            cited_set = set(cited_ids)
            
            if conflict_count > 0:
                # Conflicts always reduce confidence
                confidence = "low"
            elif "INSUFFICIENT_EVIDENCE" in raw_answer.upper():
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
                conflicts_detected=conflict_count,
            )

        except Exception as exc:
            logger.error("Synthesizer agent failed: %s. Returning fallback result.", exc)
            return SynthesisResult(
                answer_text="INSUFFICIENT_EVIDENCE",
                cited_ids=[],
                confidence="low",
                conflicts_detected=0,
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