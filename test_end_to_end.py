import asyncio
import sys
import time
import gc
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.ingest.router import IngestRouter
from services.index.embeddings import EmbeddingService
from services.index.faiss_index import FAISSIndexService
from services.retrieve.planner import QueryPlannerService
from services.retrieve.retriever import RetrievalResult
from services.retrieve.synthesizer import AnswerSynthesizerService
from services.model_manager import model_manager
from utils.validators import validate_citations


@dataclass
class QueryResult:
    query: str
    plan_ms: float = 0.0
    retrieve_ms: float = 0.0
    synth_ms: float = 0.0
    validate_ms: float = 0.0
    total_ms: float = 0.0
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    confidence: str = "low"
    citations_valid: bool = False
    evidence_count: int = 0


async def main():
    print("=" * 70)
    print("AETHER END-TO-END TEST — OPTIMIZED")
    print("=" * 70)

    # ========== STEP 0: PRE-LOAD & WARM UP MODELS ==========
    print("\n[0/4] Pre-loading models (this is the slow part, done once)...")
    t0 = time.time()
    
    # Load Granite (planner) — small, fast
    granite = model_manager.get("granite")
    print(f"   ✅ Granite ready  ({(time.time()-t0)*1000:.0f}ms)")
    
    # Load Qwen (synthesizer) — ~2.6GB, this takes 15-25s
    t0 = time.time()
    qwen = model_manager.get("qwen")
    print(f"   ✅ Qwen ready      ({(time.time()-t0)*1000:.0f}ms)")
    
    # CRITICAL: Keep Qwen resident for ALL queries. Do NOT unload between queries.
    model_manager.keep_loaded("qwen")
    
    # Warm-up: prime CPU caches and memory pages with a tiny inference
    print("   🔄 Warming up models...")
    granite.create_chat_completion(
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5, temperature=0.1,
    )
    qwen.create_chat_completion(
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5, temperature=0.1,
    )
    print("   ✅ Warm-up complete")

    # ========== STEP 1: INGEST ==========
    print("\n[1/4] Ingesting demo_bundle...")
    router = IngestRouter()
    embedder = EmbeddingService()
    faiss = FAISSIndexService(dim=1024)

    demo_dir = Path("./demo_bundle")
    if not demo_dir.exists():
        print(f"   ❌ demo_bundle not found at {demo_dir.absolute()}")
        return

    all_chunks = []
    for file_path in sorted(demo_dir.iterdir()):
        if file_path.is_file():
            chunks = await router.process_file(file_path)
            all_chunks.extend(chunks)
            print(f"   📄 {file_path.name:<35} → {len(chunks)} chunks")

    print(f"   Total: {len(all_chunks)} chunks")

    # ========== STEP 2: INDEX ==========
    print("\n[2/4] Embedding + FAISS indexing...")
    texts = [c.text for c in all_chunks]
    vectors = embedder.embed_texts(texts)
    ids = list(range(len(vectors)))
    faiss.add_vectors(vectors, ids)
    print(f"   ✅ {faiss._index.ntotal} vectors indexed")

    # ========== STEP 3: QUERY LOOP ==========
    queries = [
        "What is the voltage reading for Panel A-001?",
        "What caused the voltage fluctuation on March 15?",
        "What are the torque specifications for terminal screws?",
        "What inspection step applies to corroded terminals?",
        "Who was the inspector for Panel B-002?",
    ]

    print("\n[3/4] Running queries...")
    print("-" * 70)

    planner = QueryPlannerService()
    synth = AnswerSynthesizerService()
    results: List[QueryResult] = []

    for i, query in enumerate(queries, 1):
        print(f"\n❓ [{i}/{len(queries)}] {query}")
        query_start = time.time()

        try:
            # --- PLAN ---
            t0 = time.time()
            plan = await planner.plan_query(query)
            plan_ms = (time.time() - t0) * 1000
            print(f"   📋 Plan: {plan.primary_modality} ({plan_ms:.0f}ms)")

            # --- RETRIEVE ---
            t0 = time.time()
            query_vec = embedder.embed_texts([query])[0]
            distances, indices = faiss.search(query_vec, k=5)

            evidence = []
            for rank, (dist, idx) in enumerate(zip(distances, indices)):
                chunk = all_chunks[idx]
                # CRITICAL FIX #1: Use EID-xxx format, NOT raw numbers
                # This matches what the synthesizer prompt expects and what the validator checks
                eid = f"EID-{idx:03d}"
                evidence.append(RetrievalResult(
                    evidence_id=eid,
                    text=chunk.text,
                    source_name=Path(chunk.source_path).name,
                    page_number=chunk.page_number,
                    score=float(dist),
                    reason=f"FAISS rank {rank+1}"
                ))
            retrieve_ms = (time.time() - t0) * 1000
            print(f"   🔍 {len(evidence)} evidence pieces ({retrieve_ms:.0f}ms)")

            # --- SYNTHESIZE ---
            t0 = time.time()
            result = await synth.synthesize(
                evidence=evidence,
                query=query,
                unload_after=False,  # CRITICAL FIX #2: Keep model loaded
            )
            synth_ms = (time.time() - t0) * 1000
            print(f"   💬 {result.answer_text[:100]}...")
            print(f"   📝 Citations: {result.citations}")
            print(f"   🎯 Confidence: {result.confidence}")

            # --- VALIDATE ---
            t0 = time.time()
            valid_ids = {e.evidence_id for e in evidence}
            validation = validate_citations(result.answer_text, valid_ids)
            
            # Handle both .valid and .is_valid attribute names
            is_valid = getattr(validation, 'valid', None)
            if is_valid is None:
                is_valid = getattr(validation, 'is_valid', False)
            
            validate_ms = (time.time() - t0) * 1000
            icon = "✅" if is_valid else "⚠️"
            print(f"   {icon} Valid: {is_valid} ({validate_ms:.0f}ms)")

            total_ms = (time.time() - query_start) * 1000
            print(f"   ⏱️  Total: {total_ms:.0f}ms  (P:{plan_ms:.0f}|R:{retrieve_ms:.0f}|S:{synth_ms:.0f}|V:{validate_ms:.0f})")

            results.append(QueryResult(
                query=query,
                plan_ms=plan_ms,
                retrieve_ms=retrieve_ms,
                synth_ms=synth_ms,
                validate_ms=validate_ms,
                total_ms=total_ms,
                answer=result.answer_text,
                citations=result.citations,
                confidence=result.confidence,
                citations_valid=bool(is_valid),
                evidence_count=len(evidence),
            ))

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    # ========== STEP 4: SUMMARY ==========
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if results:
        avg_total = sum(r.total_ms for r in results) / len(results)
        avg_synth = sum(r.synth_ms for r in results) / len(results)
        valid_count = sum(1 for r in results if r.citations_valid)

        print(f"\n{'Query':<42} {'Total':>8} {'Citations':>12} {'Valid':>6}")
        print("-" * 72)
        for r in results:
            q = r.query[:40]
            c = ", ".join(r.citations) if r.citations else "NONE"
            if len(c) > 12:
                c = c[:9] + "..."
            print(f"{q:<42} {r.total_ms:>6.0f}ms {c:>12} {'✅' if r.citations_valid else '❌':>6}")
        print("-" * 72)
        print(f"{'AVERAGE':<42} {avg_total:>6.0f}ms {'':>12} {f'{valid_count}/{len(results)}':>6}")

        print(f"\nLatency Breakdown (avg):")
        print(f"   Plan:      {sum(r.plan_ms for r in results)/len(results):.0f}ms")
        print(f"   Retrieve:  {sum(r.retrieve_ms for r in results)/len(results):.0f}ms")
        print(f"   Synthesize:{avg_synth:.0f}ms  ← This should be <10s after pre-load")
        print(f"   Validate:  {sum(r.validate_ms for r in results)/len(results):.0f}ms")

        if avg_total > 8000:
            print(f"\n⚠️  Latency target is 8s. Current avg: {avg_total:.0f}ms")
            print("   If synth is still >60s, check that Qwen is actually loaded (not Mock).")
    else:
        print("No successful queries.")

    # Cleanup
    print("\n[4/4] Releasing models...")
    model_manager.release_batch("qwen")
    gc.collect()
    print("✅ Done")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())