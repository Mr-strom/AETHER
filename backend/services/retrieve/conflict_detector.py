"""Cross-source conflict detection for retrieved evidence.

Scans evidence chunks for contradictory values (numeric measurements,
dates) referencing the same entity across different source documents.
Uses regex-only extraction — no NLP libraries required.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for value extraction
# ---------------------------------------------------------------------------

# Numeric values with engineering/science units
_NUMERIC_UNIT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(V|A|W|Hz|°C|°F|psi|bar|kV|kW|mA|Ω|ohm)\b",
    re.IGNORECASE,
)

# Date patterns (MM/DD/YYYY, DD-MM-YYYY, etc.)
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
)

# Equipment / entity IDs like PANEL-A-001, TRANSFORMER-T1, UPS-UNIT-01
_ENTITY_ID_RE = re.compile(
    r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\b",
    re.IGNORECASE,
)

# Unit-type to severity mapping
_HIGH_SEVERITY_UNITS: Set[str] = {"v", "a", "w", "kv", "kw", "ma", "hz"}
_MEDIUM_SEVERITY_UNITS: Set[str] = {"°c", "°f", "psi", "bar", "ω", "ohm"}


@dataclass
class Conflict:
    """A detected contradiction between two evidence sources."""

    entity: str           # Equipment ID, e.g. "PANEL-A-001"
    metric: str           # Unit type, e.g. "V" (voltage)
    value_a: str          # e.g. "112V"
    source_a: str         # e.g. "equipment_inventory.csv"
    value_b: str          # e.g. "120V"
    source_b: str         # e.g. "equipment_inventory_v2.csv"
    evidence_id_a: str    # e.g. "EID-1"
    evidence_id_b: str    # e.g. "EID-14"
    severity: str = "high"  # "high" | "medium" | "low"


@dataclass
class _ExtractedFact:
    """Internal: a single fact extracted from one evidence chunk."""

    entity: str           # Normalised equipment ID
    value: str            # The raw numeric value string
    unit: str             # Normalised unit
    source_name: str      # Source filename
    evidence_id: str      # EID tag


class SimpleConflictDetector:
    """Detects value conflicts across evidence from different sources.

    Extraction pipeline:
    1. Find all equipment IDs in a chunk via regex.
    2. Find all numeric-with-unit values in the same chunk.
    3. Pair each equipment ID with each value found in the same chunk.
    4. Group facts by ``(entity, unit_type)``.
    5. Within each group, flag pairs from different sources with different values.
    """

    def detect(self, evidence: list) -> List[Conflict]:
        """Scan evidence for cross-source value conflicts.

        Args:
            evidence: List of RetrievalResult-like objects with
                ``.text``, ``.source_name``, and ``.evidence_id`` attributes.

        Returns:
            List of Conflict objects, one per detected contradiction.
        """
        if not evidence or len(evidence) < 2:
            return []

        # Step 1: Extract facts from all evidence chunks
        all_facts: List[_ExtractedFact] = []
        for ev in evidence:
            text = getattr(ev, "text", "")
            source = getattr(ev, "source_name", "")
            eid = getattr(ev, "evidence_id", "")
            facts = self._extract_facts(text, source, eid)
            all_facts.extend(facts)

        if not all_facts:
            return []

        # Step 2: Group by (entity, unit) and detect conflicts
        groups: Dict[Tuple[str, str], List[_ExtractedFact]] = {}
        for fact in all_facts:
            key = (fact.entity, fact.unit)
            groups.setdefault(key, []).append(fact)

        conflicts: List[Conflict] = []
        for (entity, unit), facts in groups.items():
            conflicts.extend(self._find_conflicts_in_group(entity, unit, facts))

        if conflicts:
            logger.info(
                "Conflict detector found %d conflict(s) across evidence.",
                len(conflicts),
            )

        return conflicts

    def _extract_facts(
        self, text: str, source_name: str, evidence_id: str
    ) -> List[_ExtractedFact]:
        """Extract (entity, value, unit) triples from a single chunk."""
        entities = set(m.group(1).upper() for m in _ENTITY_ID_RE.finditer(text))
        values = [
            (m.group(1), m.group(2))
            for m in _NUMERIC_UNIT_RE.finditer(text)
        ]

        if not entities or not values:
            return []

        facts: List[_ExtractedFact] = []
        for entity in entities:
            for val_str, unit_str in values:
                facts.append(_ExtractedFact(
                    entity=entity,
                    value=val_str,
                    unit=unit_str.upper(),
                    source_name=source_name,
                    evidence_id=evidence_id,
                ))

        return facts

    def _find_conflicts_in_group(
        self, entity: str, unit: str, facts: List[_ExtractedFact]
    ) -> List[Conflict]:
        """Compare facts within an (entity, unit) group for cross-source disagreements."""
        conflicts: List[Conflict] = []
        seen_pairs: Set[Tuple[str, str]] = set()  # (source_a, source_b) to avoid duplicates

        for i, fa in enumerate(facts):
            for fb in facts[i + 1:]:
                # Must be different sources
                if fa.source_name == fb.source_name:
                    continue
                # Must have different values
                if fa.value == fb.value:
                    continue

                # Avoid duplicate pairs (A,B) and (B,A)
                pair_key = tuple(sorted([fa.source_name, fb.source_name]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                severity = self._severity_for_unit(unit)

                conflicts.append(Conflict(
                    entity=entity,
                    metric=unit,
                    value_a=f"{fa.value}{unit}",
                    source_a=fa.source_name,
                    value_b=f"{fb.value}{unit}",
                    source_b=fb.source_name,
                    evidence_id_a=fa.evidence_id,
                    evidence_id_b=fb.evidence_id,
                    severity=severity,
                ))

        return conflicts

    @staticmethod
    def _severity_for_unit(unit: str) -> str:
        """Map a unit string to a conflict severity level."""
        unit_lower = unit.lower()
        if unit_lower in _HIGH_SEVERITY_UNITS:
            return "high"
        if unit_lower in _MEDIUM_SEVERITY_UNITS:
            return "medium"
        return "low"

    def format_conflicts_for_prompt(self, conflicts: List[Conflict]) -> str:
        """Format conflicts as a text block for inclusion in synthesizer prompt.

        Args:
            conflicts: List of detected Conflict objects.

        Returns:
            Human-readable conflicts block string.
        """
        if not conflicts:
            return ""

        lines = ["CONFLICTS DETECTED:"]
        for c in conflicts:
            lines.append(
                f"- {c.entity} {c.metric.lower()}: "
                f"{c.value_a} (from '{c.source_a}', {c.evidence_id_a}) vs "
                f"{c.value_b} (from '{c.source_b}', {c.evidence_id_b}) "
                f"[severity: {c.severity}]"
            )
        return "\n".join(lines)


# Module-level singleton
conflict_detector = SimpleConflictDetector()
