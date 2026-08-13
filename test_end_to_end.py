import asyncio
import hashlib
import sys
import time
import gc
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

sys.path.insert(0, str(Path(__file__).parent / "backend"))

# CRITICAL FIX: Load embeddings FIRST before llama_cpp to avoid Windows DLL conflict
from services.index.embeddings import EmbeddingService
from services.index.faiss_index import FAISSIndexService
from services.ingest.router import IngestRouter
from services.retrieve.planner import QueryPlannerService
from services.retrieve.retriever import RetrievalResult
from services.retrieve.synthesizer import AnswerSynthesizerService
from services.model_manager import model_manager
from utils.validators import validate_citations, evidence_quality_score
from services.retrieve.conflict_detector import conflict_detector


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
    hops: int = 1
    conflicts: int = 0


def _file_hash(path: Path) -> str:
    """Compute MD5 hex digest of a file for Source.file_hash."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_type(path: Path) -> str:
    """Determine file_type string from extension."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or f"application/{path.suffix.lstrip('.')}"


async def _load_evidence_from_db(
    db_ids: List[int],
    distances: List[float],
    AsyncSessionLocal,
    EvidenceChunk,
    Source,
    reason_prefix: str = "FAISS",
) -> List[RetrievalResult]:
    """Load evidence chunks from SQLite by their DB primary keys.

    Args:
        db_ids: List of EvidenceChunk.id values from FAISS/BM25 search.
        distances: Corresponding similarity scores.
        AsyncSessionLocal: Async session factory.
        EvidenceChunk: The EvidenceChunk model class.
        Source: The Source model class.
        reason_prefix: Label prefix for the reason field.

    Returns:
        List of RetrievalResult objects loaded from the database.
    """
    from sqlalchemy import select as sa_select

    evidence = []
    async with AsyncSessionLocal() as session:
        for rank, (dist, db_id) in enumerate(zip(distances, db_ids)):
            stmt = (
                sa_select(EvidenceChunk, Source.filename)
                .join(Source, EvidenceChunk.source_id == Source.id)
                .where(EvidenceChunk.id == db_id)
            )
            row = (await session.execute(stmt)).first()
            if row:
                chunk_row, source_filename = row
                evidence.append(RetrievalResult(
                    evidence_id=f"EID-{db_id}",
                    text=chunk_row.content,
                    source_name=source_filename,
                    page_number=chunk_row.page_number,
                    score=float(dist),
                    reason=f"{reason_prefix} rank {rank+1}"
                ))
    return evidence


# CRAG quality threshold: below this, reformulate the query
CRAG_QUALITY_THRESHOLD = 0.6
CRAG_MAX_HOPS = 3


async def main():
    print("=" * 70)
    print("AETHER END-TO-END TEST — CRAG PIPELINE")
    print("=" * 70)

    # ========== STEP 0: LOAD EMBEDDINGS FIRST (Windows DLL conflict fix) ==========
    print("\n[0/5] Loading embedding model first...")
    t0 = time.time()
    embedder = EmbeddingService()
    # Force model load now
    _ = embedder.embed_texts(["warmup"])
    print(f"   ✅ Embeddings ready ({(time.time()-t0)*1000:.0f}ms)")

    # ========== STEP 1: INGEST + PERSIST TO SQLITE ==========
    print("\n[1/5] Ingesting demo_bundle + persisting to SQLite...")
    router = IngestRouter()
    faiss = FAISSIndexService(dim=1024)

    demo_dir = Path("./demo_bundle")
    if not demo_dir.exists():
        print(f"   ❌ demo_bundle not found at {demo_dir.absolute()}")
        return

    # --- Create DB schema ---
    from backend.models.database import Base, engine, AsyncSessionLocal
    from backend.models.source import Source
    from backend.models.evidence import EvidenceChunk

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("   ✅ SQLite schema created")

    # --- Ingest files and persist ---
    all_chunks = []           # IngestChunk objects (from extractors)
    db_chunk_ids: List[int] = []  # DB primary keys after insert
    file_chunks_map = {}      # file_path -> list of IngestChunks

    for file_path in sorted(demo_dir.iterdir()):
        if file_path.is_file():
            chunks = await router.process_file(file_path)
            file_chunks_map[file_path] = chunks
            all_chunks.extend(chunks)
            print(f"   📄 {file_path.name:<35} → {len(chunks)} chunks")

    print(f"   Total: {len(all_chunks)} chunks")

    # --- Write Source + EvidenceChunk records to SQLite ---
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for file_path, chunks in file_chunks_map.items():
                # Create Source record
                source = Source(
                    filename=file_path.name,
                    file_type=_file_type(file_path),
                    file_path=str(file_path.absolute()),
                    file_hash=_file_hash(file_path),
                    size_bytes=file_path.stat().st_size,
                    status="indexed",
                )
                session.add(source)
                await session.flush()  # Assigns source.id

                # Create EvidenceChunk records
                for chunk in chunks:
                    ec = EvidenceChunk(
                        source_id=source.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.text,
                        modality=chunk.modality,
                        page_number=chunk.page_number,
                    )
                    session.add(ec)
                    await session.flush()  # Assigns ec.id
                    db_chunk_ids.append(ec.id)

    print(f"   ✅ {len(db_chunk_ids)} chunks persisted to SQLite")

    # ========== STEP 2: INDEX (using DB primary keys) ==========
    print("\n[2/5] Embedding + FAISS indexing...")
    texts = [c.text for c in all_chunks]
    vectors = embedder.embed_texts(texts)
    faiss.add_vectors(vectors, db_chunk_ids)
    print(f"   ✅ {faiss._index.ntotal} vectors indexed (IDs: {db_chunk_ids[0]}..{db_chunk_ids[-1]})")

    # ========== STEP 2b: BM25 INDEX ==========
    print("\n[2b/5] Building BM25 index...")
    from backend.services.index.bm25_index import bm25_index_service
    bm25_items = [(db_id, chunk.text) for db_id, chunk in zip(db_chunk_ids, all_chunks)]
    bm25_index_service.build_index(bm25_items)
    print(f"   ✅ BM25 index built with {len(bm25_items)} documents")

    # ========== STEP 2c: SAVE INDICES TO DISK ==========
    print("\n[2c/5] Saving indices to disk...")
    faiss.save()
    print(f"   ✅ FAISS index saved to {faiss.index_path}")
    bm25_index_service.save()
    print(f"   ✅ BM25 index saved to ./data/bm25_index.pkl")

    # ========== STEP 2d: INJECT CONFLICTING DOCUMENT ==========
    print("\n[2d/5] Injecting conflicting document for conflict detection demo...")
    conflict_csv_path = demo_dir / "equipment_inventory_v2.csv"
    conflict_csv_content = (
        "equipment_id,location,install_date,last_inspection,status,voltage_reading,inspector\n"
        "PANEL-A-001,Building-7-Floor-3,2022-01-10,2024-04-01,PASS,120,K.Lee\n"
        "PANEL-B-002,Building-7-Floor-3,2022-01-10,2024-04-01,PASS,119,K.Lee\n"
    )
    conflict_csv_path.write_text(conflict_csv_content)

    # Ingest, embed, persist the conflicting file
    conflict_chunks = await router.process_file(conflict_csv_path)
    print(f"   📄 {conflict_csv_path.name:<35} → {len(conflict_chunks)} chunks")

    conflict_db_ids: List[int] = []
    async with AsyncSessionLocal() as session:
        async with session.begin():
            conflict_source = Source(
                filename=conflict_csv_path.name,
                file_type=_file_type(conflict_csv_path),
                file_path=str(conflict_csv_path.absolute()),
                file_hash=_file_hash(conflict_csv_path),
                size_bytes=conflict_csv_path.stat().st_size,
                status="indexed",
            )
            session.add(conflict_source)
            await session.flush()
            for chunk in conflict_chunks:
                ec = EvidenceChunk(
                    source_id=conflict_source.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.text,
                    modality=chunk.modality,
                    page_number=chunk.page_number,
                )
                session.add(ec)
                await session.flush()
                conflict_db_ids.append(ec.id)

    # Add to FAISS + BM25
    conflict_texts = [c.text for c in conflict_chunks]
    conflict_vectors = embedder.embed_texts(conflict_texts)
    faiss.add_vectors(conflict_vectors, conflict_db_ids)
    bm25_items_v2 = [(db_id, c.text) for db_id, c in zip(conflict_db_ids, conflict_chunks)]
    # Rebuild BM25 with all documents
    all_bm25 = [(db_id, chunk.text) for db_id, chunk in zip(db_chunk_ids, all_chunks)]
    all_bm25.extend(bm25_items_v2)
    bm25_index_service.build_index(all_bm25)

    print(f"   ⚠️  Conflicting document injected (Panel A-001: 120V vs original 112V)")
    print(f"   ✅ {len(conflict_db_ids)} conflict chunks added (total: {faiss._index.ntotal} vectors)")

    # ========== STEP 3: PRE-LOAD LLM MODELS (after embeddings are loaded) ==========
    print("\n[3/5] Pre-loading LLM models...")
    t0 = time.time()
    granite = model_manager.get("granite")
    print(f"   ✅ Granite ready  ({(time.time()-t0)*1000:.0f}ms)")
    
    t0 = time.time()
    qwen = model_manager.get("qwen")
    print(f"   ✅ Qwen ready      ({(time.time()-t0)*1000:.0f}ms)")
    
    model_manager.keep_loaded("qwen")
    
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

    # ========== STEP 4: QUERY LOOP WITH CRAG ==========
    queries = [
        "What is the voltage reading for Panel A-001?",
        "What caused the voltage fluctuation on March 15?",
        "What are the torque specifications for terminal screws?",
        "What inspection step applies to corroded terminals?",
        "Who was the inspector for Panel B-002?",
    ]

    print("\n[4/5] Running queries with CRAG loop (max %d hops)..." % CRAG_MAX_HOPS)
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

            # --- CRAG RETRIEVAL LOOP ---
            t0 = time.time()
            merged_evidence: dict[str, RetrievalResult] = {}  # evidence_id -> RetrievalResult
            current_queries = [query]
            hop_count = 0
            quality_score = 0.0
            quality_feedback = ""

            for hop in range(1, CRAG_MAX_HOPS + 1):
                hop_count = hop

                # Retrieve for all current queries
                new_evidence = []
                for q in current_queries:
                    query_vec = embedder.embed_texts([q])[0]
                    distances, indices = faiss.search(query_vec, k=5)
                    hop_evidence = await _load_evidence_from_db(
                        indices, distances,
                        AsyncSessionLocal, EvidenceChunk, Source,
                        reason_prefix=f"Hop{hop}",
                    )
                    new_evidence.extend(hop_evidence)

                # Deduplicate: add only new evidence IDs
                new_count = 0
                for ev in new_evidence:
                    if ev.evidence_id not in merged_evidence:
                        merged_evidence[ev.evidence_id] = ev
                        new_count += 1

                all_evidence = list(merged_evidence.values())
                quality_score, quality_feedback = evidence_quality_score(all_evidence)

                if hop == 1:
                    status = "sufficient" if quality_score >= CRAG_QUALITY_THRESHOLD else "weak"
                    print(f"   🔍 Hop {hop}: {len(all_evidence)} evidence pieces (score: {quality_score:.2f}) → {status}")
                else:
                    status = "sufficient" if quality_score >= CRAG_QUALITY_THRESHOLD else "weak"
                    print(f"   🔍 Hop {hop}: +{new_count} new, {len(all_evidence)} total (score: {quality_score:.2f}) → {status}")

                # If quality is sufficient, stop hopping
                if quality_score >= CRAG_QUALITY_THRESHOLD:
                    break

                # If not the last hop, reformulate
                if hop < CRAG_MAX_HOPS:
                    reformulated = await planner.reformulate_query(query, quality_feedback)
                    # Filter out the original query to avoid duplicate retrieval
                    reformulated = [q for q in reformulated if q.lower() != query.lower()]
                    if not reformulated:
                        reformulated = [query]  # Fallback
                    print(f"   🔄 Reformulating: {reformulated}")
                    current_queries = reformulated

            retrieve_ms = (time.time() - t0) * 1000
            evidence = list(merged_evidence.values())

            # --- CONFLICT DETECTION ---
            detected_conflicts = conflict_detector.detect(evidence)
            if detected_conflicts:
                print(f"   ⚠️  {len(detected_conflicts)} conflict(s) detected:")
                for cf in detected_conflicts:
                    print(f"      {cf.entity} {cf.metric.lower()}: {cf.value_a} ({cf.source_a}) vs {cf.value_b} ({cf.source_b})")
            else:
                print(f"   ✅ No conflicts detected")

            # --- SYNTHESIZE ---
            t0 = time.time()
            result = await synth.synthesize(
                evidence=evidence,
                query=query,
                unload_after=False,
                conflicts=detected_conflicts if detected_conflicts else None,
            )
            synth_ms = (time.time() - t0) * 1000
            print(f"   💬 {result.answer_text[:120]}...")
            print(f"   📝 Citations: {result.cited_ids}")
            print(f"   🎯 Confidence: {result.confidence}")
            if result.conflicts_detected:
                print(f"   ⚡ Conflicts in answer: {result.conflicts_detected}")

            # --- VALIDATE ---
            t0 = time.time()
            valid_ids = {e.evidence_id for e in evidence}
            validation = validate_citations(result.answer_text, valid_ids)
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
                citations=result.cited_ids,
                confidence=result.confidence,
                citations_valid=bool(is_valid),
                evidence_count=len(evidence),
                hops=hop_count,
                conflicts=len(detected_conflicts),
            ))

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    # ========== SUMMARY ==========
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if results:
        avg_total = sum(r.total_ms for r in results) / len(results)
        avg_synth = sum(r.synth_ms for r in results) / len(results)
        valid_count = sum(1 for r in results if r.citations_valid)

        print(f"\n{'Query':<42} {'Total':>8} {'Hops':>5} {'Cnfl':>5} {'Citations':>14} {'Valid':>6}")
        print("-" * 84)
        for r in results:
            q = r.query[:40]
            c = ", ".join(r.citations) if r.citations else "NONE"
            if len(c) > 14:
                c = c[:11] + "..."
            cnfl = f"{r.conflicts}" if r.conflicts else "-"
            print(f"{q:<42} {r.total_ms:>6.0f}ms {r.hops:>5} {cnfl:>5} {c:>14} {'✅' if r.citations_valid else '❌':>6}")
        print("-" * 84)
        avg_hops = sum(r.hops for r in results) / len(results)
        total_conflicts = sum(r.conflicts for r in results)
        print(f"{'AVERAGE':<42} {avg_total:>6.0f}ms {avg_hops:>5.1f} {total_conflicts:>5} {'':>14} {f'{valid_count}/{len(results)}':>6}")

        print(f"\nLatency Breakdown (avg):")
        print(f"   Plan:      {sum(r.plan_ms for r in results)/len(results):.0f}ms")
        print(f"   Retrieve:  {sum(r.retrieve_ms for r in results)/len(results):.0f}ms")
        print(f"   Synthesize:{avg_synth:.0f}ms")
        print(f"   Validate:  {sum(r.validate_ms for r in results)/len(results):.0f}ms")

        if avg_total > 8000:
            print(f"\n⚠️  Latency target is 8s. Current avg: {avg_total:.0f}ms")
            print("   If synth is still >60s, check that Qwen is actually loaded (not Mock).")
    else:
        print("No successful queries.")

    # ========== AIRGAP VERIFICATION ==========
    print("\n" + "=" * 70)
    print("🔒 AIRGAP VERIFICATION")
    print("=" * 70)

    from services.attestation import full_attestation
    t0 = time.time()
    attestation = full_attestation()
    attest_ms = (time.time() - t0) * 1000

    # Manifest
    m_icon = "✅" if attestation["signature_valid"] else "❌"
    print(f"\n   {m_icon} Manifest valid:    {attestation['signature_valid']}")
    if attestation["attestation_hash"]:
        print(f"   🔑 Attestation hash: {attestation['attestation_hash']}")
    if attestation["file_results"]:
        for fname, info in attestation["file_results"].items():
            f_icon = "✅" if info["match"] else "❌"
            print(f"      {f_icon} {fname}: {info['actual']}")

    # Network
    n_icon = "✅" if attestation["network_isolated"] else "❌"
    print(f"\n   {n_icon} Network isolated:  {attestation['network_isolated']}")
    if attestation["warnings"]:
        for w in attestation["warnings"]:
            print(f"      ⚠️  {w}")

    # Errors
    if attestation["errors"]:
        print(f"\n   Errors:")
        for e in attestation["errors"]:
            print(f"      ❌ {e}")

    # All green
    ag_icon = "🔒" if attestation["all_green"] else "🔓"
    print(f"\n   {ag_icon} ALL GREEN: {attestation['all_green']} ({attest_ms:.0f}ms)")

    # ========== CLEANUP ==========
    print("\n[5/5] Releasing models + closing DB + cleanup...")
    model_manager.release_batch("qwen")
    gc.collect()
    # Remove temp conflicting CSV
    if conflict_csv_path.exists():
        conflict_csv_path.unlink()
        print("   🗑️  Removed temp conflict file: equipment_inventory_v2.csv")
    await engine.dispose()
    print("✅ Done")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())