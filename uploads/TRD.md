# AETHER — Technical Requirements Document (TRD)
**Version:** 1.0  
**Date:** 2026-08-10  
**Hardware:** ASUS ROG Zephyrus G14 (2022) — Ryzen 7 6800HS, 16GB RAM, RX 6700S 8GB VRAM, 1TB SSD  
**OS:** Windows 11 (primary) / Ubuntu 22.04 (WSL2 fallback for ROCm experiments)

---

## 1. Architecture Overview

AETHER is a layered, agentic system with 4 distinct phases: **Ingest → Index → Retrieve → Validate/Synthesize**. Each phase is modular, testable, and replaceable. The system uses a **smart model manager** to keep only one large model in memory at a time, swapping via disk on demand.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              REACT EVIDENCE VIEWER                           │
│  (Chat Panel + Evidence Cards + Conflict Graph + Uncertainty Meter)         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI ORCHESTRATION LAYER                        │
│  /api/query  /api/sources/*  /api/evidence/*  /api/system/*  /api/evaluate  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC REASONING ENGINE                             │
│  ┌─────────┐   ┌───────────┐   ┌─────────────┐   ┌─────────────────┐      │
│  │ Planner │ → │ Retriever │ → │  Validator  │ → │   Synthesizer   │      │
│  │ (Phi-4) │   │(Hybrid    │   │  (CRAG     │   │  (Qwen3-8B)     │      │
│  │ 3.8B    │   │ FAISS+    │   │  Grader)    │   │                 │      │
│  │         │   │ BM25+     │   │             │   │                 │      │
│  │         │   │ Graph)    │   │             │   │                 │      │
│  └─────────┘   └───────────┘   └─────────────┘   └─────────────────┘      │
│       ↑                                               ↓                     │
│       └────────────── Re-retrieve loop (max 3) ───────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HYBRID EVIDENCE STORE                                │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ FAISS Vector│  │ SQLite +     │  │ BM25 FTS    │  │ Evidence Graph  │  │
│  │ Index       │  │ NetworkX     │  │ (whoosh/    │  │ (Entity/Date/   │  │
│  │ (BGE-M3 +   │  │ (Metadata +  │  │ rank-bm25)  │  │ Conflict edges) │  │
│  │ ColQwen)    │  │  Provenance) │  │             │  │                 │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                                   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐ │
│  │ Native │ │ PDF    │ │ OCR +  │ │whisper.│ │ Video  │ │ Evidence     │ │
│  │ Parser │ │ Render │ │ Layout │ │ cpp    │ │ Keyframe│ │ Normalizer   │ │
│  │(PyMuPDF│ │→ Image │ │(Tess/  │ │ ASR    │ │ Sampler │ │ (Schema      │ │
│  │docx etc)│ │       │ │Paddle) │ │        │ │        │ │  Validation)  │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hardware Strategy & AMD GPU Reality

### 2.1 The RX 6700S Problem

The RX 6700S (8GB) is a **gaming GPU, not a compute GPU**. Critical facts:
- **No official ROCm support** on Windows for RX 6000 mobile chips
- ROCm on Linux supports RX 6700S only via community patches (unstable)
- llama.cpp **Vulkan backend** works on AMD but ~30-50% slower than CUDA equivalent
- PyTorch DirectML is experimental and limited

### 2.2 Recommended Strategy: CPU-Primary, GPU-Opportunistic

| Component | Runtime | Backend | Reason |
|-----------|---------|---------|--------|
| Text LLM (Qwen3-8B) | CPU | llama.cpp (AVX2) | Ryzen 7 6800HS is 8C/16T Zen 3+. 4-bit 8B runs at ~8-12 tok/s. Reliable. |
| Planner (Phi-4-mini) | CPU | llama.cpp (AVX2) | 3.8B model, very fast on CPU. |
| VLM (Qwen2.5-VL-3B) | GPU | llama.cpp Vulkan | 3B fits in 8GB VRAM. Vulkan backend functional. |
| Vision Embeddings (ColQwen) | GPU | llama.cpp Vulkan or CPU | Batch processing during ingest, not query-time. |
| Text Embeddings (BGE-M3) | CPU | ONNX Runtime or sentence-transformers | Fast enough on CPU. No GPU needed. |
| Reranker (BGE-Reranker) | CPU | ONNX Runtime | Tiny model, CPU is fine. |
| ASR (whisper.cpp) | CPU | whisper.cpp (AVX/NEON) | Optimized for CPU. Tiny/Base models very fast. |

### 2.3 Model Memory Management

With 16GB RAM, only **ONE** large model (4-8B) can be loaded at once.

**Smart Model Manager (SMM):**
- Models stored on SSD as `.gguf` files
- At query time, SMM loads only the model needed for current agent
- Model swap time: ~1.5-2.5s from SSD (NVMe ~3.5GB/s read)
- During ingest (batch), models stay loaded until batch completes
- RAM budget: 14GB max (2GB reserved for OS + app overhead)

```
RAM Budget (16GB total):
├── OS + App overhead:        ~2.0 GB
├── Active model (8B 4-bit):  ~5.5 GB
├── FAISS index (in-mem):    ~1.5 GB (for 10K documents)
├── SQLite + Graph cache:     ~0.5 GB
├── Evidence artifacts cache: ~1.0 GB (thumbnails, crops)
├── Working buffers:          ~2.0 GB
└── Free headroom:            ~3.5 GB
```

---

## 3. Data Model

### 3.1 SourceDocument

```python
class SourceDocument:
    id: UUID                    # Primary key
    sha256: str                 # SHA-256 of original file
    original_name: str          # User-facing filename
    mime_type: str              # MIME type
    file_size_bytes: int
    imported_at: datetime
    sensitivity: Enum           # public | internal | restricted
    status: Enum                # indexed | partial | quarantined | failed
    artifact_dir: str           # Path to extracted artifacts
    page_count: int | None      # For paginated docs
    duration_ms: int | None     # For audio/video
    error_log: str | None       # If status != indexed
```

### 3.2 EvidenceUnit

```python
class EvidenceUnit:
    id: UUID                    # Primary key
    source_id: UUID             # FK → SourceDocument
    modality: Enum              # text | table | image | audio | video_frame | metadata
    page_number: int | None
    start_ms: int | None        # For audio/video
    end_ms: int | None
    text: str | None            # Extracted text / transcript
    bbox: [x1, y1, x2, y2] | None  # Normalized 0-1 coordinates
    artifact_path: str | None   # Path to image crop / audio clip / frame
    extraction_method: str      # e.g., "pymupdf_native", "tesseract_ocr", "whisper_cpp"
    extraction_confidence: float # 0.0–1.0
    content_hash: str           # SHA-256 of text+artifact
    embedding_id: int | None    # FAISS internal ID
    created_at: datetime
```

### 3.3 EvidenceRelation (Graph Edges)

```python
class EvidenceRelation:
    id: UUID
    source_unit_id: UUID        # FK → EvidenceUnit
    target_unit_id: UUID        # FK → EvidenceUnit
    relation_type: Enum         # supports | contradicts | same_entity | temporally_before | references
    confidence: float           # 0.0–1.0
    extracted_by: str           # Model/rule that created this edge
    created_at: datetime
```

### 3.4 RetrievalHit

```python
class RetrievalHit:
    evidence_id: UUID
    semantic_score: float       # FAISS cosine similarity
    lexical_score: float        # BM25 score (normalized)
    graph_score: float          # Graph proximity boost
    rerank_score: float         # Cross-encoder final score
    composite_score: float      # Weighted combination
    reason: str                 # Human-readable why this was retrieved
```

### 3.5 AnswerRecord

```python
class AnswerRecord:
    id: UUID
    query: str
    query_vector: List[float]   # For audit
    answer_text: str
    evidence_ids: List[UUID]
    confidence: Enum            # high | medium | low | insufficient
    per_claim_scores: List[dict] # [{"claim": "...", "score": 0.92, "evidence_ids": [...]}]
    contradictions: List[str]   # Detected conflict descriptions
    unknowns: List[str]         # What evidence is missing
    retrieval_hops: int         # How many CRAG loops (1-3)
    network_mode: Enum          # offline_core | disconnected_sync | connected_enhancement
    latency_ms: int
    created_at: datetime
```

---

## 4. API Specification

### 4.1 Core Endpoints

| Method | Route | Request | Response | Description |
|--------|-------|---------|----------|-------------|
| POST | `/api/sources/import` | `{path: str, options: dict}` | `{job_id: UUID, status: str, file_count: int}` | Import folder or file. Returns async job ID. |
| GET | `/api/sources` | — | `List[SourceDocument]` | List all sources with status. |
| DELETE | `/api/sources/{id}` | — | `{deleted: bool, rebuilt_index: bool}` | Remove source + cascade delete. |
| GET | `/api/sources/{id}/status` | — | `{status: str, progress_pct: float, errors: List[str]}` | Poll import progress. |
| POST | `/api/query` | `{query: str, filters: dict, modality_hint: str}` | `AnswerRecord` | Main query endpoint. |
| POST | `/api/query/stream` | Same as /query | SSE stream | Streaming answer with evidence cards. |
| GET | `/api/evidence/{id}` | — | `EvidenceUnit + preview` | Get evidence metadata + preview. |
| GET | `/api/evidence/{id}/artifact` | — | Binary stream | Stream image crop / audio clip / PDF page. |
| GET | `/api/evidence/{id}/context` | — | `List[EvidenceUnit]` | Get neighboring evidence (same page, adjacent time). |
| POST | `/api/evaluate/run` | `{question_set: str}` | `{recall: float, precision: float, abstention_rate: float}` | Run golden question set. |
| GET | `/api/system/status` | — | `{network_mode: str, models_loaded: List[str], ram_usage_mb: int, gpu_usage_mb: int, index_stats: dict}` | System health. |
| POST | `/api/system/verify-airgap` | — | `{attestation_hash: str, timestamp: str, signature_valid: bool}` | Cryptographic offline proof. |
| POST | `/api/sync/export` | `{source_ids: List[UUID], password: str}` | `{bundle_path: str, bundle_hash: str}` | Create encrypted signed bundle. |
| POST | `/api/sync/import` | `{bundle_path: str, password: str}` | `{imported: int, failed: int}` | Import signed bundle. |

### 4.2 Query Request Schema

```json
{
  "query": "Which inspection step applies to the photographed panel?",
  "filters": {
    "sources": ["uuid-1", "uuid-2"],
    "modalities": ["text", "image"],
    "date_range": {"from": "2024-01-01", "to": "2024-12-31"}
  },
  "modality_hint": "auto",
  "max_evidence": 5,
  "require_abstention": false
}
```

### 4.3 Query Response Schema

```json
{
  "id": "uuid-answer-001",
  "query": "Which inspection step applies to the photographed panel?",
  "answer_text": "The panel matches Inspection Step 4-B [EID-042]...",
  "evidence_ids": ["eid-042", "eid-087", "eid-156"],
  "confidence": "high",
  "per_claim_scores": [
    {"claim": "Panel matches Step 4-B", "score": 0.94, "evidence_ids": ["eid-042"]},
    {"claim": "Terminal block is corroded", "score": 0.71, "evidence_ids": ["eid-087"]}
  ],
  "contradictions": ["Voice note says 'corroded' but manual says 'clean'"],
  "unknowns": ["No evidence confirms panel serial number"],
  "retrieval_hops": 1,
  "network_mode": "offline_core",
  "latency_ms": 6200,
  "created_at": "2026-08-10T14:30:00Z"
}
```

---

## 5. Ingestion Pipeline Detail

### 5.1 File Type Router

```
Input File
    ↓
[Hash + MIME Validation] → SHA-256, magic bytes check
    ↓
[Security Scan] → Size < 100MB, decompression bomb check, macro scan
    ↓
[Type Router]
    ├── PDF → PyMuPDF (native text) → [Visual check?] → Render page → OCR (Tesseract)
    ├── DOCX → python-docx → Native text + table extraction
    ├── XLSX/CSV → pandas → Table rows as evidence units
    ├── TXT/MD → Direct → Chunked
    ├── Image (PNG/JPG) → [OCR?] → Tesseract/PaddleOCR + full image as evidence unit
    ├── Audio (WAV/MP3) → whisper.cpp → Transcript segments with timestamps
    └── Video (MP4) → ffmpeg keyframe sampler + whisper.cpp transcript → Paired evidence
```

### 5.2 Visual Information Detection

For PDFs, after native text extraction, run a heuristic:
- If page has < 50 chars of text → likely scanned/image-heavy → force OCR + page-image embedding
- If page has tables/diagrams → render + OCR + ColQwen embedding
- If page is text-dense → text-only path (faster)

### 5.3 Evidence Normalization

All extracted content normalized to EvidenceUnit schema:
- Text: cleaned, deduplicated whitespace, max 2048 chars per unit
- Images: max 1024px longest side, WebP format, preserve aspect ratio
- Audio: 16kHz mono WAV for whisper, original kept for playback
- Video: keyframes as WebP, 1 per 5 seconds or scene-change detected

---

## 6. Retrieval Engine Detail

### 6.1 Hybrid Retrieval Formula

```python
composite_score = (
    0.50 * semantic_score +      # FAISS vector similarity (BGE-M3 text, ColQwen image)
    0.25 * lexical_score +       # BM25 keyword match
    0.15 * graph_score +         # Graph proximity (entity co-occurrence)
    0.10 * temporal_score        # Time proximity (for timeline queries)
)
```

### 6.2 Query Router Logic (Planner Agent)

The Planner (Phi-4-mini 3.8B) classifies the query intent:

| Query Signal | Route | Retrieval Strategy |
|--------------|-------|-------------------|
| "according to", "where", "which section", "quote" | Text + Metadata | BM25-heavy, page-level retrieval |
| "what does this image show", "diagram", "photo", "compare image" | Vision | ColQwen visual retrieval → VLM reasoning |
| "what was said", "voice note", "at what time" | Audio | Transcript window + timestamp retrieval |
| "when did", "sequence", "timeline" | Temporal | Graph date nodes + chronological sort |
| "calculate", "count", "sum" | Deterministic | Calculator tool + LLM explains result |
| Ambiguous / multi-part | Decomposed | Planner breaks into sub-queries, parallel retrieval |

### 6.3 CRAG Validation Loop

```python
def validate_and_synthesize(retrieved_evidence, query):
    for hop in range(1, 4):
        # Grade evidence
        sufficiency = grade_sufficiency(evidence, query)   # 0-1
        relevance = grade_relevance(evidence, query)       # 0-1  
        consistency = grade_consistency(evidence)          # 0-1

        composite = 0.4*sufficiency + 0.35*relevance + 0.25*consistency

        if composite >= 0.7:
            # Good enough — synthesize answer
            return synthesize(evidence, query)

        if hop < 3:
            # Reformulate query and re-retrieve
            reformulated = planner.reformulate(query, evidence, why_weak=composite)
            evidence = retriever.search(reformulated)

    # All hops exhausted — abstain
    return abstain(query, evidence, reason="insufficient_evidence_quality")
```

### 6.4 ColQwen Visual Retrieval

ColQwen2.5-3B treats each PDF page as an image, tokenizes it into visual patches, and creates late-interaction embeddings. At query time:
1. If query contains visual terms ("diagram", "photo", "show me"), or user uploads an image
2. ColQwen embeds the query (or query image) into visual tokens
3. Late interaction: token-level similarity between query and page patches
4. Returns top-k page images most visually similar to query
5. These page images are fed to Qwen2.5-VL-3B for detailed understanding

**Why this wins:** Most competitors do OCR → text RAG. They lose all visual layout, diagrams, and spatial relationships. ColQwen retrieves by **visual similarity**, preserving the full page context.

---

## 7. Agentic Orchestration

### 7.1 Agent Definitions

| Agent           | Model                            | Role                                                            | Input                       | Output                                                |
| --------------- | -------------------------------- | --------------------------------------------------------------- | --------------------------- | ----------------------------------------------------- |
| **Planner**     | Phi-4-mini 3.8B (Q4_K_M)         | Decompose query, select modalities, set retrieval params        | User query + system context | Query plan (modality, filters, decomposition)         |
| **Retriever**   | Deterministic + BGE-M3 + ColQwen | Execute hybrid search, rerank, format context                   | Query plan                  | Top-5 evidence units with scores                      |
| **Validator**   | Phi-4-mini 3.8B (Q4_K_M)         | Grade evidence quality, detect conflicts, decide if re-retrieve | Evidence + original query   | Validation report (scores, conflicts, recommendation) |
| **Synthesizer** | Qwen3-8B-A3B (Q4_K_M)            | Generate cited answer, abstain if needed                        | Validated evidence + query  | Answer text with inline citations                     |

### 7.2 Agent State Machine

```
[USER_QUERY]
    ↓
[PLANNER] → QueryPlan {modality, filters, sub_queries}
    ↓
[RETRIEVER] → EvidenceContext {units: List[EvidenceUnit], scores: List[float]}
    ↓
[VALIDATOR] → ValidationReport {sufficiency, relevance, consistency, conflicts, recommendation}
    ↓
    ├── recommendation == "synthesize" → [SYNTHESIZER] → Answer
    ├── recommendation == "re_retrieve" AND hops < 3 → [PLANNER reformulates] → loop
    └── recommendation == "abstain" OR hops == 3 → AbstentionResponse
```

### 7.3 System Prompts (Core)

**Planner System Prompt:**
```
You are the Query Planner for an offline evidence system. 
Analyze the user's question and output a JSON plan with:
- "primary_modality": "text" | "vision" | "audio" | "temporal" | "mixed"
- "sub_queries": list of simpler questions to answer the main question
- "filters": {"sources": [...], "modalities": [...], "date_range": {...}}
- "requires_calculation": true/false
- "explanation": why you chose this plan
```

**Synthesizer System Prompt (Grounding Contract):**
```
You are an evidence synthesizer. You have access ONLY to the evidence units provided below.
Rules:
1. Every factual claim MUST cite one or more evidence IDs in brackets [EID-xxx].
2. If evidence is insufficient, return exactly: INSUFFICIENT_EVIDENCE
3. If evidence conflicts, present both sides and state which has higher confidence.
4. Do not use outside knowledge. Do not invent citations.
5. End with an "Unknowns" section listing what evidence is missing.
```

---

## 8. Offline Security & Attestation

### 8.1 Cryptographic Airgap Verification

At install time:
1. Compute SHA-256 of every model file (.gguf) and index file
2. Store hashes in `manifest.json` signed with Ed25519 private key
3. Public key embedded in application binary

At runtime (judge clicks "Verify Airgap"):
1. Recompute SHA-256 of all models + indexes
2. Compare against signed manifest
3. Verify no network interfaces have active routes (except loopback)
4. Display green certificate with timestamp + hash chain

### 8.2 Network Isolation

```python
def verify_offline_mode():
    # Check all network interfaces
    for iface in psutil.net_if_addrs():
        if iface != "lo" and has_ip_address(iface):
            return False, f"Interface {iface} has IP"

    # Check DNS resolution attempt (should fail)
    try:
        socket.gethostbyname("google.com")
        return False, "DNS resolution succeeded"
    except:
        pass

    # Check manifest integrity
    if not verify_manifest_hashes():
        return False, "Manifest integrity failed"

    return True, "Airgap verified"
```

---

## 9. Technology Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Backend | Python + FastAPI | 3.11+ | Async, OpenAPI auto-docs |
| LLM Runtime | llama-cpp-python | latest | Vulkan backend for AMD GPU |
| Embeddings | sentence-transformers + BGE-M3 | latest | CPU-optimized |
| Vision Embeddings | ColQwen2.5-3B via llama.cpp | latest | Converted to GGUF |
| VLM | Qwen2.5-VL-3B via llama.cpp | latest | Vulkan backend |
| ASR | whisper.cpp (Python bindings) | latest | Tiny/Base models |
| Vector DB | FAISS (faiss-cpu) | latest | IVF index for 10K+ docs |
| Graph | NetworkX + SQLite | built-in | In-memory graph, SQLite persistence |
| FTS | rank-bm25 + whoosh | latest | Fallback lexical search |
| OCR | Tesseract 5 + pytesseract | 5.x | English default, +1 lang stretch |
| PDF | PyMuPDF (fitz) | latest | Fast text + image extraction |
| DOCX | python-docx | latest | Native structure preservation |
| Video | ffmpeg-python | latest | Keyframe extraction |
| Frontend | React 18 + Tailwind CSS | latest | Evidence viewer + chat |
| State | Zustand | latest | Lightweight global state |
| Charts | D3.js or vis-network | latest | Conflict graph visualization |
| Crypto | cryptography (Python) | latest | Ed25519 signing, AES bundle encryption |

---

## 10. Model Specifications

| Model | Size | Quantization | RAM/VRAM | Download | Purpose |
|-------|------|--------------|----------|----------|---------|
| Phi-4-mini-instruct | 3.8B | Q4_K_M | ~2.5 GB | HuggingFace → GGUF | Planner + Validator |
| Qwen3-8B-A3B (MoE) | 8B total, 3B active | Q4_K_M | ~5.5 GB | HuggingFace → GGUF | Synthesizer |
| Qwen2.5-VL-3B-Instruct | 3B | Q4_K_M | ~2.2 GB | HuggingFace → GGUF | Vision reasoning |
| ColQwen2.5-3B | 3B | Q4_K_M | ~2.2 GB | HuggingFace → GGUF | Visual page retrieval |
| BGE-M3 | 568M | FP16 | ~1.1 GB | sentence-transformers | Text embeddings |
| BGE-Reranker-base | 278M | FP16 | ~0.6 GB | sentence-transformers | Reranking |
| whisper.cpp tiny | 39M | Q5_0 | ~0.05 GB | whisper.cpp | Audio transcription |
| whisper.cpp base | 74M | Q5_0 | ~0.1 GB | whisper.cpp | Better accuracy (optional) |

**Total model storage:** ~15 GB on SSD (well within 1TB)

---

## 11. Error Handling & Resilience

| Scenario | Handling |
|----------|----------|
| Model fails to load | Fallback to smaller model (e.g., Qwen3-4B if 8B fails). Log error. |
| OCR returns garbage | Confidence score < 0.3 → discard, flag for manual review. |
| Audio is noisy/unintelligible | whisper.cpp returns low confidence → shorter segments, flag uncertainty. |
| Two sources contradict | Validator detects via entity matching → surface both, confidence-weighted. |
| File import fails (corrupt) | Quarantine file, log error, continue with remaining files. |
| Query timeout (>30s) | Return partial evidence with "Search timed out, showing best effort results." |
| Out of memory during inference | SMM unloads non-essential models, retry with smaller context window. |

---

## 12. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Cold start (app open → first query) | ≤ 20s | Time to load Planner + Retriever |
| Query latency (text-only) | ≤ 8s | From submit to first token |
| Query latency (vision) | ≤ 15s | Includes VLM loading + inference |
| Ingest throughput (PDF text) | ≥ 10 pages/sec | Batch mode, native text |
| Ingest throughput (OCR) | ≥ 2 pages/sec | Tesseract on CPU |
| Ingest throughput (audio) | ≥ 2x realtime | whisper.cpp tiny |
| Model swap time | ≤ 2.5s | From SSD (NVMe) |
| Index query time | ≤ 200ms | FAISS + BM25 + Graph for 10K units |
