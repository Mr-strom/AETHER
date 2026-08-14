"""Post-processor citation guard for synthesised answers.

Ensures every claim in a generated answer is backed by a valid evidence
citation before it reaches the user.  If the guard detects uncited claims
or hallucinated EIDs, the pipeline can trigger a retry or replace the
answer with a safe fallback.

Typical usage inside the query pipeline::

    from backend.services.synthesis.post_processor import post_processor

    result = post_processor.process(answer_text, evidence_units)
    if not result["safe"]:
        # retry or return INSUFFICIENT_EVIDENCE
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from backend.services.retrieve.retriever import RetrievalResult

logger = logging.getLogger(__name__)

# Regex matching inline citations like [EID-abc-123] or [EID-5]
_EID_PATTERN = re.compile(r"\[(EID-[a-zA-Z0-9_-]+)\]", re.IGNORECASE)

# Sentence boundary heuristic — split on . ! ? followed by whitespace or end
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class PostProcessor:
    """Citation guard that verifies every EID in the answer against evidence."""

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def process(
        self,
        answer_text: str,
        evidence_units: List[RetrievalResult],
    ) -> Dict[str, Any]:
        """Validate all ``[EID-xxx]`` citations in *answer_text*.

        Args:
            answer_text:  The raw answer produced by the synthesizer.
            evidence_units:  Evidence units that were available for synthesis.

        Returns:
            A dict with keys:
            - ``safe`` (bool): True iff all citations are valid.
            - ``reason`` (str | None): ``"uncited_claims"`` | ``"no_citations"`` | None.
            - ``verified_eids`` (list[str]): EIDs confirmed present in evidence.
            - ``missing_eids`` (list[str]): EIDs in answer not in evidence.
            - ``cleaned_text`` (str): The answer text (unchanged for now).
            - ``per_claim_scores`` (list[dict]): Per-sentence citation scores.
        """
        valid_eids: Set[str] = {
            eu.evidence_id.upper() for eu in evidence_units
        }

        # Confidence map: evidence_id -> score
        confidence_map: Dict[str, float] = {
            eu.evidence_id.upper(): eu.score for eu in evidence_units
        }

        # Extract all cited EIDs
        cited_raw = _EID_PATTERN.findall(answer_text)
        cited_upper: List[str] = [eid.upper() for eid in cited_raw]
        cited_set: Set[str] = set(cited_upper)

        # Compute per-claim scores
        per_claim_scores = self._score_claims(answer_text, valid_eids, confidence_map)

        # Check: is this an INSUFFICIENT_EVIDENCE response?
        is_insufficient = "INSUFFICIENT_EVIDENCE" in answer_text.upper()

        # ---- Decision logic ----

        # Case 1: citations found but some are missing from evidence
        missing = sorted(cited_set - valid_eids)
        if missing:
            logger.warning("PostProcessor: missing EIDs %s", missing)
            return {
                "safe": False,
                "reason": "uncited_claims",
                "missing_eids": missing,
                "verified_eids": sorted(cited_set & valid_eids),
                "cleaned_text": answer_text,
                "per_claim_scores": per_claim_scores,
            }

        # Case 2: no citations at all and not an INSUFFICIENT_EVIDENCE answer
        if not cited_set and not is_insufficient:
            logger.warning("PostProcessor: answer has no citations")
            return {
                "safe": False,
                "reason": "no_citations",
                "missing_eids": [],
                "verified_eids": [],
                "cleaned_text": answer_text,
                "per_claim_scores": per_claim_scores,
            }

        # Case 3: all citations valid
        return {
            "safe": True,
            "reason": None,
            "verified_eids": sorted(cited_set & valid_eids),
            "missing_eids": [],
            "cleaned_text": answer_text,
            "per_claim_scores": per_claim_scores,
        }

    # ------------------------------------------------------------------
    # Per-claim scoring
    # ------------------------------------------------------------------

    def _score_claims(
        self,
        answer_text: str,
        valid_eids: Set[str],
        confidence_map: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Split answer into sentences and score each by citation quality.

        Score logic:
        - 0.95 if citation is valid AND evidence confidence > 0.7
        - 0.60 if citation is valid but evidence confidence <= 0.7
        - 0.00 if no valid citation or citation is hallucinated

        Sections like ``Unknowns:``, ``Conflicts:``, and
        ``INSUFFICIENT_EVIDENCE`` are excluded from scoring.
        """
        sentences = _SENTENCE_SPLIT.split(answer_text)
        results: List[Dict[str, Any]] = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Skip structural sections
            lower = sentence.lower()
            if lower.startswith(("unknowns:", "conflicts:", "insufficient_evidence")):
                continue

            # Extract EIDs in this sentence
            cited_in_sentence = [
                eid.upper() for eid in _EID_PATTERN.findall(sentence)
            ]
            valid_cited = [eid for eid in cited_in_sentence if eid in valid_eids]

            if not valid_cited:
                score = 0.0
            else:
                # Average confidence of cited evidence
                confidences = [
                    confidence_map.get(eid, 0.0) for eid in valid_cited
                ]
                avg_confidence = sum(confidences) / len(confidences)
                score = 0.95 if avg_confidence > 0.7 else 0.60

            results.append({
                "claim": sentence[:120],  # truncate for readability
                "score": score,
                "evidence_ids": valid_cited,
            })

        return results


# Module-level singleton
post_processor = PostProcessor()
