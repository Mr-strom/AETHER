"""Contextual Retrieval — two-pass chunk enrichment using Granite.

Implements Anthropic's Contextual Retrieval technique:
1. Summarize the full document once (first ~1500 tokens).
2. For each chunk, generate 30-50 words of situating context.
3. Prepend context to chunk text → ``index_text`` for embedding + BM25.

The raw ``text`` field is preserved unchanged for UI display.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List

from backend.services.model_manager import model_manager

logger = logging.getLogger(__name__)


class Contextualizer:
    """Two-pass contextual retrieval enricher using Granite (resident model)."""

    def __init__(self) -> None:
        self.model_name = "granite"
        self._loaded_here = False

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        """Load granite if not already loaded. Track if WE loaded it."""
        loaded = model_manager.get_loaded_models()
        if self.model_name not in loaded:
            logger.info("Contextualizer: loading granite model...")
            try:
                model_manager.load(self.model_name)
                self._loaded_here = True
                logger.info("Contextualizer: granite loaded.")
            except Exception as exc:
                logger.warning("Contextualizer: failed to load granite: %s", exc)
                raise

    def _maybe_unload(self) -> None:
        """Unload granite only if WE loaded it (not if it was already loaded)."""
        if self._loaded_here:
            logger.info("Contextualizer: unloading granite (we loaded it).")
            model_manager.unload(self.model_name)
            self._loaded_here = False

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _chat(self, system: str, user: str, max_tokens: int = 120) -> str:
        """Send a chat completion request to granite and return content."""
        model = model_manager.get(self.model_name)
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return response["choices"][0]["message"]["content"].strip()

    # ------------------------------------------------------------------
    # Pass 1: Document summary
    # ------------------------------------------------------------------

    def summarize_document(self, chunks: List[str]) -> str:
        """Generate a 2-3 sentence summary from the first ~1500 tokens.

        Args:
            chunks: List of chunk texts in document order.

        Returns:
            Summary string (single paragraph, no newlines).
        """
        self._ensure_model()

        # Concatenate chunks up to ~1500 tokens (rough: 4 chars/token → 6000 chars)
        full_text = ""
        for chunk in chunks:
            if len(full_text) + len(chunk) > 6000:
                break
            full_text += chunk + "\n\n"

        system = (
            "You are a document summarizer. Write a concise 2-3 sentence summary. "
            "Focus on what the document is about, who wrote it, and key topics. "
            "Answer with ONLY the summary, no preamble."
        )
        user = f"{full_text[:6000]}\n\nSummary:"

        summary = self._chat(system, user, max_tokens=120)
        summary = summary.replace("\n", " ").strip()
        logger.info(
            "Contextualizer: generated summary (%d chars): %s...",
            len(summary), summary[:100],
        )
        return summary

    # ------------------------------------------------------------------
    # Pass 2: Per-chunk context
    # ------------------------------------------------------------------

    def contextualize_chunk(self, doc_summary: str, chunk_text: str) -> str:
        """Generate situating context and prepend it to the chunk.

        Args:
            doc_summary: Document-level summary from pass 1.
            chunk_text: Raw chunk text.

        Returns:
            ``"<context> <chunk_text>"`` or raw chunk_text on failure.
        """
        # Skip very short chunks — not worth the LLM call
        if len(chunk_text.strip()) < 20:
            logger.debug("Contextualizer: skipping contextualization for short chunk (%d chars).", len(chunk_text))
            return chunk_text

        system = (
            "You are improving search retrieval for a document chunk. "
            "Given a document summary and a chunk, write a short context (30-50 words) "
            "that situates this chunk within the overall document. "
            "Include entity names, dates, or section references if relevant. "
            "Answer with ONLY the context text, nothing else."
        )
        user = (
            f"Document summary: {doc_summary}\n\n"
            f"Chunk: {chunk_text[:800]}\n\n"
            "Context:"
        )

        try:
            context = self._chat(system, user, max_tokens=100)

            # Clean up — remove quotes, "Context:" prefix
            context = re.sub(r"^(Context:?\s*)", "", context, flags=re.IGNORECASE)
            context = context.strip('"').strip("'").strip()

            if not context or len(context) < 10:
                logger.warning("Contextualizer: fallback to raw text (reason: empty/short context).")
                return chunk_text

            contextualized = f"{context} {chunk_text}"
            logger.debug(
                "Contextualizer: chunk contextualized (%d → %d chars).",
                len(chunk_text), len(contextualized),
            )
            return contextualized

        except Exception as exc:
            logger.warning("Contextualizer: fallback to raw text (reason: %s).", exc)
            return chunk_text

    # ------------------------------------------------------------------
    # Rule-based fallback (no LLM needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_based_context(chunks: List[str]) -> List[str]:
        """Prepend first sentence of document to each chunk as cheap context.

        Used when granite model is unavailable or crashes.
        """
        # Extract first meaningful sentence from the document
        first_text = ""
        for chunk in chunks:
            stripped = chunk.strip()
            if len(stripped) > 30:
                # Take first sentence (up to first period, question mark, or 120 chars)
                for i, ch in enumerate(stripped):
                    if ch in ".!?" and i > 20:
                        first_text = stripped[: i + 1]
                        break
                if not first_text:
                    first_text = stripped[:120]
                break

        if not first_text:
            logger.info("Contextualizer: rule-based fallback has no usable first sentence.")
            return list(chunks)

        logger.info(
            "Contextualizer: using rule-based fallback (%d chars): %s...",
            len(first_text), first_text[:80],
        )
        results = []
        for chunk in chunks:
            if len(chunk.strip()) < 20:
                results.append(chunk)
            else:
                results.append(f"{first_text} {chunk}")
        return results

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def contextualize_document(self, chunks: List[str]) -> List[str]:
        """Run two-pass contextualization on all chunks of one document.

        Args:
            chunks: List of raw chunk texts in document order.

        Returns:
            List of contextualized chunks (same order, same length).
        """
        if not chunks:
            return []

        start_time = time.time()

        try:
            summary = self.summarize_document(chunks)
        except Exception as exc:
            logger.warning(
                "Contextualizer: granite model unavailable (%s). "
                "Falling back to rule-based context.", exc,
            )
            return self._rule_based_context(chunks)

        results = []
        for chunk in chunks:
            ctx_chunk = self.contextualize_chunk(summary, chunk)
            results.append(ctx_chunk)

        elapsed = time.time() - start_time
        logger.info("Contextualizer: processed %d chunks in %.1fs.", len(chunks), elapsed)

        self._maybe_unload()
        return results
