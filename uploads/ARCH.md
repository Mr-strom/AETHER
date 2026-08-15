# AETHER — Full Architecture & Deployment Diagram
**Version:** 1.0 | **Date:** 2026-08-10

---

## 1. SYSTEM CONTEXT DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL ENTITIES                                  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   User      │    │   Judge     │    │   USB Drive │    │   Admin     │ │
│  │ (Field      │    │ (Competition│    │ (Sync       │    │ (Bundle     │ │
│  │  Worker)    │    │  Verifier)  │    │  Transfer)  │    │  Manager)   │ │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘ │
│         │ asks questions   │ verifies offline │ imports/exports  │ manages  │
│         │ views evidence   │ runs tests       │ signed bundles   │ sources  │
└─────────┼──────────────────┼──────────────────┼──────────────────┼────────┘
          │                  │                  │                  │
          └──────────────────┴──────────────────┴──────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AETHER SYSTEM BOUNDARY                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     REACT EVIDENCE VIEWER                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │   │
│  │  │ Chat Panel  │  │ Evidence    │  │ Conflict    │  │ System   │ │   │
│  │  │ (Streaming) │  │ Cards       │  │ Graph       │  │ Status   │ │   │
│  │  │             │  │ (Page/Region│  │ (vis-network│  │ (Airgap  │ │   │
│  │  │             │  │ /Timestamp) │  │ )           │  │ Verify)  │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓ HTTP/SSE                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FASTAPI ORCHESTRATION LAYER                      │   │
│  │  /api/sources/*  /api/query  /api/evidence/*  /api/system/*        │   │
│  │  /api/evaluate  /api/sync/*                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓ Internal API                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     AGENTIC REASONING ENGINE                         │   │
│  │                                                                     │   │
│  │  ┌─────────┐     ┌───────────┐     ┌─────────────┐     ┌────────┐ │   │
│  │  │ Planner │────→│ Retriever │────→│  Validator  │────→│Synth.  │ │   │
│  │  │ (Phi-4) │     │(Hybrid     │     │  (CRAG      │     │(Qwen3) │ │   │
│  │  │ 3.8B    │     │ FAISS+    │     │  Grader)    │     │ 8B     │ │   │
│  │  │ CPU     │     │ BM25+     │     │ CPU         │     │ CPU    │ │   │
│  │  │         │     │ Graph)    │     │             │     │        │ │   │
│  │  └────┬────┘     └─────┬─────┘     └──────┬──────┘     └───┬────┘ │   │
│  │       │                │                  │                │      │   │
│  │       └────────────────┴──────────────────┴────────────────┘      │   │
│  │                         ↑ Re-retrieve loop (max 3)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     HYBRID EVIDENCE STORE                            │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────┐ │   │
│  │  │ FAISS Vector│  │ SQLite +     │  │ BM25 FTS    │  │ Evidence│ │   │
│  │  │ Index       │  │ NetworkX     │  │ (rank-bm25) │  │ Graph   │ │   │
│  │  │ (BGE-M3 +   │  │ (Metadata +  │  │             │  │ (Entity │ │   │
│  │  │ ColQwen)    │  │  Provenance) │  │             │  │ /Date/  │ │   │
│  │  │             │  │              │  │             │  │ Conflict│ │   │
│  │  └─────────────┘  └──────────────┘  └─────────────┘  └─────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     INGESTION PIPELINE                               │   │
│  │                                                                     │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐ │   │
│  │  │ Native │ │ PDF    │ │ OCR +  │ │whisper.│ │ Video  │ │Evidence│  │   │
│  │  │ Parser │ │ Render │ │ Layout │ │ cpp    │ │ Keyframe│ │Norm.  │  │   │
│  │  │(PyMuPDF│ │→ Image │ │(Tess/  │ │ ASR    │ │ Sampler │ │       │  │   │
│  │  │docx etc)│ │       │ │Paddle) │ │        │ │        │ │       │  │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └──────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SMART MODEL MANAGER (SMM)                        │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │   │
│  │  │ Phi-4-mini  │  │ Qwen3-8B    │  │ Qwen2.5-VL  │  │ ColQwen   │ │   │
│  │  │ (Planner +  │  │ (Synthesizer│  │ (Vision     │  │ (Visual   │ │   │
│  │  │  Validator) │  │ )           │  │  Reasoning) │  │  Retrieval)│  │   │
│  │  │  ~2.5GB     │  │  ~5.5GB     │  │  ~2.2GB     │  │  ~2.2GB   │ │   │
│  │  │  CPU        │  │  CPU        │  │  GPU Vulkan │  │  GPU/CPU  │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │   │
│  │                                                                     │   │
│  │  RULE: Only ONE large model in RAM at a time. Swap from SSD.       │   │
│  │  RAM Budget: 14GB max. 2GB reserved for OS.                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↑↓                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     LOCAL STORAGE (1TB SSD)                          │   │
│  │                                                                     │   │
│  │  /aether/                                                           │   │
│  │  ├── models/          (15 GB)  — All GGUF models                    │   │
│  │  ├── indexes/         (500 MB) — FAISS + BM25 + graph               │   │
│  │  ├── artifacts/       (50 GB)  — Thumbnails, crops, audio clips     │   │
│  │  ├── sources/         (100 GB) — Original files (read-only)         │   │
│  │  ├── db.sqlite        (1 GB)   — SQLite metadata + graph            │   │
│  │  └── manifest.json    (1 KB)   — Signed attestation manifest        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. DEPLOYMENT ARCHITECTURE

### 2.1 Single-Node Deployment (Target: ASUS ROG G14)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASUS ROG Zephyrus G14                        │
│                    Windows 11 / Ubuntu 22.04                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CPU: AMD Ryzen 7 6800HS (8C/16T, Zen 3+)             │   │
│  │  RAM: 16 GB DDR5                                      │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  llama.cpp (CPU backend, AVX2)                │   │   │
│  │  │  ├── Phi-4-mini (Planner + Validator)         │   │   │
│  │  │  ├── Qwen3-8B (Synthesizer)                   │   │   │
│  │  │  └── whisper.cpp (Audio transcription)        │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  Python FastAPI (async, uvicorn)              │   │   │
│  │  │  ├── Ingestion Pipeline                       │   │   │
│  │  │  ├── Hybrid Retriever                         │   │   │
│  │  │  ├── Agent Orchestrator                       │   │   │
│  │  │  └── API Routes                               │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  FAISS-cpu + SQLite + NetworkX                │   │   │
│  │  │  ├── Text embeddings (BGE-M3)                 │   │   │
│  │  │  ├── BM25 lexical index                       │   │   │
│  │  │  └── Evidence graph                           │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  GPU: AMD Radeon RX 6700S (8GB VRAM)                  │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  llama.cpp (VULKAN backend)                   │   │   │
│  │  │  ├── Qwen2.5-VL-3B (Vision reasoning)         │   │   │
│  │  │  └── ColQwen2.5-3B (Visual retrieval)         │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │  NOTE: ROCm not supported. Vulkan is the only GPU     │   │
│  │  compute path for AMD RX 6000 mobile on Windows.      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Storage: 1TB NVMe SSD                                │   │
│  │  ├── /aether/models/     (15 GB)                      │   │
│  │  ├── /aether/indexes/    (500 MB)                     │   │
│  │  ├── /aether/artifacts/  (50 GB)                      │   │
│  │  ├── /aether/sources/    (100 GB)                     │   │
│  │  └── /aether/db.sqlite   (1 GB)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Browser: Chrome/Edge (localhost:5173)                │   │
│  │  ├── React 18 + Tailwind + Zustand                    │   │
│  │  ├── Chat Panel + Evidence Cards                      │   │
│  │  ├── Conflict Graph (vis-network)                     │   │
│  │  └── System Status + Airgap Verify                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Process Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PROCESS LAYOUT                             │
│                                                                 │
│  Main Process (Python FastAPI)                                  │
│  ├── Uvicorn workers: 1 (single-node, avoid RAM duplication)    │
│  ├── Background tasks: asyncio.create_task() for ingestion      │
│  └── Subprocesses:                                              │
│      ├── ffmpeg (video keyframe extraction)                     │
│      ├── tesseract (OCR)                                       │
│      └── whisper.cpp (audio transcription)                      │
│                                                                 │
│  Model Lifecycle (Smart Model Manager):                         │
│  ├── On startup: Load Phi-4-mini (Planner is first touchpoint)  │
│  ├── On query:                                                 │
│  │   ├── Planner already loaded → use immediately               │
│  │   ├── Retriever (deterministic, no model) → execute         │
│  │   ├── Validator: Phi-4-mini already loaded → use            │
│  │   ├── If weak evidence: Planner reformulates (loaded)       │
│  │   └── Synthesizer: Load Qwen3-8B → generate → unload        │
│  ├── On visual query:                                          │
│  │   ├── Load ColQwen (GPU) → embed query → search → unload    │
│  │   └── If VLM needed: Load Qwen2.5-VL (GPU) → reason → unload│
│  └── On audio query:                                           │
│      └── whisper.cpp runs in subprocess, no model manager needed │
│                                                                 │
│  RAM State During Typical Text Query:                           │
│  ├── Phi-4-mini:     ~2.5 GB (always resident)                 │
│  ├── Qwen3-8B:       ~5.5 GB (loaded on demand, 2s swap)       │
│  ├── FAISS index:    ~1.5 GB (loaded at startup)               │
│  ├── SQLite cache:   ~0.5 GB                                   │
│  ├── App overhead:   ~2.0 GB                                   │
│  └── Free:           ~4.0 GB headroom                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. DATA FLOW DIAGRAMS

### 3.1 Ingestion Flow

```
[User drops folder]
    ↓
[FastAPI /api/sources/import]
    ↓
[File Walker] → List files, compute MIME, validate
    ↓
[Security Scan] → Size check, decompression bomb, macro scan
    ↓
[Type Router]
    ├── PDF → [PyMuPDF Native Text] → [Visual Heuristic?]
    │                           ↓ Yes (low text / diagrams)
    │                     [Render Page → Image]
    │                           ↓
    │                     [OCR Tesseract] → [Bounding Boxes]
    │                           ↓
    │                     [ColQwen Embed] → Visual FAISS
    │                           ↓
    │                     [Evidence Normalizer]
    ├── DOCX → [python-docx] → [Text + Tables] → [Evidence Normalizer]
    ├── TXT/MD → [Direct Read] → [Chunk] → [Evidence Normalizer]
    ├── CSV/XLSX → [pandas] → [Row-wise] → [Evidence Normalizer]
    ├── Image → [OCR?] → [Tesseract] → [Evidence Normalizer]
    │       → [Full Image] → [ColQwen Embed] → Visual FAISS
    ├── Audio → [whisper.cpp] → [Segments + Timestamps] → [Evidence Normalizer]
    └── Video → [ffmpeg Keyframes] → [Image Evidence]
          → [Audio Track] → [whisper.cpp] → [Paired Evidence]
    ↓
[Evidence Normalizer] → Validate schema, compute content_hash
    ↓
[Text Embed] → BGE-M3 → Text FAISS
    ↓
[Graph Extract] → Entity/Date extraction → NetworkX edges
    ↓
[BM25 Index] → rank-bm25 inverted index
    ↓
[SQLite Persist] → All metadata + graph + relations
    ↓
[Import Complete] → Status: indexed / partial / failed
```

### 3.2 Query Flow

```
[User submits query]
    ↓
[FastAPI /api/query]
    ↓
[Planner Agent (Phi-4-mini)]
    ├── Decomposes query
    ├── Classifies modality
    └── Sets filters
    ↓
[Modality Router]
    ├── Text path → [Text FAISS] + [BM25] + [Graph traversal]
    ├── Vision path → [ColQwen visual search] + [Text FAISS]
    ├── Audio path → [BM25 on transcripts] + [Timestamp filter]
    └── Temporal path → [Graph date nodes] + [Chronological sort]
    ↓
[Merge & Deduplicate] → Union of all paths, unique EvidenceUnits
    ↓
[Reranker (BGE-Reranker)] → Top-20 → Top-5
    ↓
[Format Context] → Evidence block with [EID-xxx] prefixes
    ↓
[Validator Agent (Phi-4-mini)]
    ├── Grades sufficiency, relevance, consistency
    ├── Detects conflicts
    └── Recommends: synthesize / re_retrieve / abstain
    ↓
    ├── [Re_retrieve] AND hops < 3
    │       ↓
    │   [Planner Reformulate] → [Retriever] → [Validator] → loop
    │
    ├── [Abstain] OR hops == 3
    │       ↓
    │   [Abstention Response] → "INSUFFICIENT_EVIDENCE" + reason
    │
    └── [Synthesize]
            ↓
        [Synthesizer Agent (Qwen3-8B)]
            ├── Receives validated evidence + query
            ├── Generates answer with inline [EID-xxx] citations
            └── Ends with "Unknowns:" section
            ↓
        [Post-Processor]
            ├── Regex extract all [EID-xxx]
            ├── Verify each exists in retrieved evidence
            ├── Reject if uncited claims found
            └── Compute per-claim confidence scores
            ↓
        [Answer Record]
            ├── answer_text, evidence_ids, confidence
            ├── per_claim_scores, contradictions, unknowns
            ├── retrieval_hops, latency_ms, network_mode
            └── created_at
            ↓
        [React Evidence Viewer]
            ├── Renders answer with clickable citations
            ├── Shows evidence cards in right panel
            ├── Displays confidence badges
            └── Highlights conflicts and unknowns
```

### 3.3 Offline Attestation Flow

```
[Install Time]
    ↓
[Generate Ed25519 Keypair]
    ├── Private key: stored in secure enclave / encrypted file
    └── Public key: embedded in application binary
    ↓
[Compute Manifest]
    ├── For each model in ./models/: {name, path, sha256}
    └── Sign manifest with private key → manifest.json
    ↓
[Store manifest.json] in /aether/manifest.json

[Runtime — Judge clicks "Verify Airgap"]
    ↓
[/api/system/verify-airgap]
    ├── Step 1: Recompute SHA-256 of all model files
    │   └── Compare with manifest → signature_valid?
    ├── Step 2: Check network interfaces (psutil.net_if_addrs())
    │   └── Only "lo" (loopback) should have IP address
    ├── Step 3: Attempt DNS resolution (socket.gethostbyname)
    │   └── Must fail (timeout or NXDOMAIN)
    └── Step 4: Check no active internet routes
    ↓
[Return JSON]
    {
      "attestation_hash": "sha256_of_current_state",
      "timestamp": "2026-08-10T14:30:00Z",
      "signature_valid": true,
      "network_isolated": true,
      "all_green": true
    }
    ↓
[Frontend]
    ├── If all_green: show green certificate modal
    ├── Display attestation hash, timestamp
    └── QR code of hash (optional, for external verification)
```

---

## 4. COMPONENT INTERFACES

### 4.1 Agent Interface Contract

```python
class Agent(ABC):
    @abstractmethod
    async def process(self, input_data: dict, context: dict) -> dict:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def ram_requirement_mb(self) -> int:
        pass

class PlannerAgent(Agent):
    model_name = "Phi-4-mini-instruct"
    ram_requirement_mb = 2500

    async def process(self, query: str, context: dict) -> QueryPlan:
        pass

class RetrieverService:
    async def retrieve(self, plan: QueryPlan, max_results: int = 5) -> RetrievalResult:
        pass

class ValidatorAgent(Agent):
    model_name = "Phi-4-mini-instruct"
    ram_requirement_mb = 2500

    async def process(self, evidence: RetrievalResult, query: str) -> ValidationReport:
        pass

class SynthesizerAgent(Agent):
    model_name = "Qwen3-8B-A3B"
    ram_requirement_mb = 5500

    async def process(self, evidence: RetrievalResult, query: str) -> SynthesisResult:
        pass
```

### 4.2 Smart Model Manager Interface

```python
class SmartModelManager:
    async def load(self, model_name: str) -> ModelHandle:
        pass

    async def unload(self, model_name: str) -> None:
        pass

    async def get(self, model_name: str) -> ModelHandle:
        pass

    def get_ram_usage(self) -> dict:
        pass

    def can_load(self, model_name: str) -> bool:
        pass
```

---

## 5. FAILURE MODE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    FAILURE HANDLING LAYER                       │
│                                                                 │
│  [Model Load Failure]                                           │
│  ├── Qwen3-8B fails → Fallback to Qwen3-4B (if available)     │
│  ├── Qwen2.5-VL fails → Skip visual path, use text-only       │
│  ├── ColQwen fails → Skip visual retrieval, use OCR text only  │
│  └── All models fail → Return 503, log error, suggest restart  │
│                                                                 │
│  [Retrieval Failure]                                            │
│  ├── FAISS returns empty → Fallback to BM25 only               │
│  ├── BM25 returns empty → Fallback to graph traversal          │
│  ├── All empty → Validator recommends abstain                  │
│  └── Timeout (>5s) → Return partial results with warning       │
│                                                                 │
│  [Generation Failure]                                           │
│  ├── Synthesizer timeout (>20s) → Return evidence list only    │
│  ├── Post-processor rejects (uncited claims) → Retry once      │
│  ├── Retry fails → Return evidence + "Unable to synthesize"    │
│  └── Model hallucinates citation → Validator catches, abstains │
│                                                                 │
│  [Security Failure]                                             │
│  ├── File too large (>100MB) → Reject, quarantine              │
│  ├── Decompression bomb → Reject, alert user                   │
│  ├── Macro detected → Reject, do not process                   │
│  └── Import crash → Log error, mark source as failed, continue │
│                                                                 │
│  [Hardware Failure]                                             │
│  ├── Out of RAM → Unload non-essential models, retry           │
│  ├── Disk full → Alert user, pause ingestion                   │
│  └── GPU crash → Fallback to CPU for all models                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. SECURITY ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                              │
│                                                                 │
│  Layer 1: Input Sanitization                                    │
│  ├── MIME type validation (python-magic, not extension)        │
│  ├── File size limits (100MB per file, 1GB per bundle)         │
│  ├── Decompression bomb detection (zipfile, tarfile limits)    │
│  └── Macro/script scanning (oletools for Office docs)          │
│                                                                 │
│  Layer 2: Sandboxed Processing                                  │
│  ├── All converters run in subprocess with timeout             │
│  ├── Resource limits: CPU time, RAM, disk write                │
│  └── Network isolation: subprocess cannot access network       │
│                                                                 │
│  Layer 3: Read-Only Evidence                                    │
│  ├── Original files in /aether/sources/ are NEVER modified     │
│  ├── All artifacts written to /aether/artifacts/               │
│  └── Hash verification on every access                         │
│                                                                 │
│  Layer 4: Offline Guarantee                                     │
│  ├── Core system has no network dependencies                   │
│  ├── Network status monitored continuously                     │
│  ├── Cloud mode is opt-in, clearly labeled, separate code path │
│  └── Cryptographic attestation proves integrity                │
│                                                                 │
│  Layer 5: Output Safety                                         │
│  ├── Post-processor rejects uncited claims                     │
│  ├── Abstention preferred over hallucination                   │
│  ├── Confidence scores prevent overstatement                   │
│  └── Conflict detection prevents one-sided narratives          │
└─────────────────────────────────────────────────────────────────┘
```
