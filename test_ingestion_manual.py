import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.ingest.router import IngestRouter
from services.ingest.schema import IngestChunk
from services.index.embeddings import EmbeddingService
from services.index.faiss_index import FAISSIndexService
import json

async def main():
    router = IngestRouter()
    embedder = EmbeddingService()
    faiss = FAISSIndexService(dim=1024)
    
    demo_dir = Path("./demo_bundle")
    all_chunks = []
    
    print("=" * 60)
    print("MANUAL INGESTION TEST")
    print("=" * 60)
    
    for file_path in sorted(demo_dir.iterdir()):
        if file_path.is_file():
            print(f"\n📄 Processing: {file_path.name}")
            try:
                chunks = await router.process_file(file_path)  # FIXED: was route_and_extract
                print(f"   ✅ Extracted {len(chunks)} chunks")
                for i, chunk in enumerate(chunks[:3]):  # Show first 3
                    preview = chunk.text[:80].replace("\n", " ")
                    print(f"      Chunk {i}: [{chunk.modality}] {preview}...")
                if len(chunks) > 3:
                    print(f"      ... and {len(chunks)-3} more")
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL CHUNKS: {len(all_chunks)}")
    print(f"{'=' * 60}")
    
    # Test embedding
    if all_chunks:
        print("\n🔢 Embedding chunks...")
        texts = [c.text for c in all_chunks]
        vectors = embedder.embed_texts(texts)
        print(f"   ✅ Generated {len(vectors)} embeddings")
        print(f"   Vector shape: {len(vectors[0])} dimensions")
        
        # Add to FAISS
        print("\n📦 Adding to FAISS index...")
        ids = list(range(len(vectors)))
        faiss.add_vectors(vectors, ids)
        print(f"   ✅ Index now has {faiss._index.ntotal} vectors")
        
        # Test search
        print("\n🔍 Testing search...")
        query = "What is the voltage reading for Panel A-001?"
        query_vec = embedder.embed_texts([query])[0]
        distances, indices = faiss.search(query_vec, k=5)
        print(f"   Query: '{query}'")
        print(f"   Top 5 results:")
        for rank, (dist, idx) in enumerate(zip(distances, indices)):
            chunk = all_chunks[idx]
            preview = chunk.text[:60].replace("\n", " ")
            print(f"      {rank+1}. [score={dist:.3f}] {preview}...")
        
        # Save index
        faiss.save("./demo_index")
        print(f"\n💾 Index saved to ./demo_index")
    
    print("\n🎉 Ingestion pipeline test complete!")

if __name__ == "__main__":
    asyncio.run(main())