# AETHER — Project Memory Card
**Paste this into any new AI chat to continue the project.**

---

## PROJECT IDENTITY

**Name:** AETHER (Adaptive Evidence-based Trusted Hybrid Engine for Retrieval)  
**Type:** Offline multimodal RAG evidence workspace  
**Competition:** CMR231 — Offline Multimodal RAG  
**Build Time:** 1 month  
**Team:** Solo developer  
**Hardware:** ASUS ROG Zephyrus G14 (2022) — Ryzen 7 6800HS, 16GB RAM, RX 6700S 8GB VRAM, 1TB SSD, Windows 11

---

## WHAT WE ARE BUILDING

A fully offline application that:
1. **Ingests** mixed files (PDF, DOCX, TXT, MD, CSV, XLSX, PNG, JPG, WAV, MP3, MP4)
2. **Indexes** them with 4 retrieval strategies: semantic (FAISS/BGE-M3), lexical (BM25), visual (ColQwen), graph (NetworkX/SQLite)
3. **Answers** natural language questions using ONLY local evidence
4. **Proves** every claim with inline citations [EID-xxx] linking to exact page/region/timestamp
5. **Admits** when evidence is insufficient (returns `INSUFFICIENT_EVIDENCE`)
6. **Works** with WiFi completely disabled — cryptographic attestation proves this

**The 6 Secret Weapons:**
1. ColQwen visual page retrieval (retrieves by image similarity, not just OCR text)
2. 4-Agent orchestration (Planner → Retriever → Validator → Synthesizer)
3. CRAG self-correction (re-retrieves if evidence quality < 0.7, max 3 hops)
4. Evidence provenance graph (entities, dates, conflicts as network)
5. Per-claim confidence scoring (HIGH/MEDIUM/LOW/UNSUPPORTED)
6. Cryptographic offline attestation (SHA-256 manifest, judge-verifiable)

---

## ARCHITECTURE SNAPSHOT

```
User Query
    ↓
Planner Agent (Phi-4-mini 3.8B, CPU)
    ↓
[Modality Router] → Text | Vision | Audio | Temporal
    ↓
Hybrid Retrieval (FAISS + BM25 + Graph)
    ↓
Reranker (BGE-Reranker, CPU)
    ↓
Validator Agent (CRAG grading, CPU)
    ↓
[Weak?] → Re-retrieve (max 3 hops) → [Still weak?] → ABSTAIN
    ↓
Synthesizer Agent (Qwen3-8B-A3B 4-bit, CPU)
    ↓
React Evidence Viewer (chat + evidence cards + conflict graph)
```

---

## MODEL STACK

| Model | Size | Quant | Where | Purpose |
|-------|------|-------|-------|---------|
| Phi-4-mini-instruct | 3.8B | Q4_K_M | CPU (llama.cpp) | Planner + Validator |
| Qwen3-8B-A3B (MoE) | 8B total, 3B active | Q4_K_M | CPU (llama.cpp) | Synthesizer |
| Qwen2.5-VL-3B | 3B | Q4_K_M | GPU Vulkan (llama.cpp) | Vision reasoning |
| ColQwen2.5-3B | 3B | Q4_K_M | GPU Vulkan or CPU | Visual page retrieval |
| BGE-M3 | 568M | FP16 | CPU (ONNX) | Text embeddings |
| BGE-Reranker-base | 278M | FP16 | CPU (ONNX) | Reranking |
| whisper.cpp tiny | 39M | Q5_0 | CPU | Audio transcription |

**Smart Model Manager:** Only ONE large model in RAM at a time. Swap from SSD in <2.5s. RAM budget: 14GB max.

**AMD GPU Reality:** RX 6700S has NO official ROCm support on Windows. Strategy: CPU-primary for LLMs (Ryzen 7 6800HS is 8C/16T, handles 4-bit 8B at ~8-12 tok/s). GPU used only for VLM via llama.cpp Vulkan backend.

---

## TECH STACK

- **Backend:** Python 3.11, FastAPI, async
- **LLM Runtime:** llama-cpp-python (Vulkan backend for AMD)
- **Embeddings:** sentence-transformers (BGE-M3), FAISS-cpu
- **Vision:** ColQwen2.5-3B → GGUF via llama.cpp
- **ASR:** whisper.cpp (Python bindings)
- **OCR:** Tesseract 5 + pytesseract
- **PDF:** PyMuPDF
- **Graph:** NetworkX + SQLite
- **FTS:** rank-bm25
- **Frontend:** React 18, Tailwind CSS, Zustand, D3.js/vis-network
- **Crypto:** cryptography library (Ed25519 + AES)

---

## KEY FILES (Already Created)

1. `PRD.md` — Product Requirements Document (goals, user stories, functional requirements, success metrics)
2. `TRD.md` — Technical Requirements Document (architecture, data models, API specs, model specs, AMD GPU strategy)
3. `SCOPE.md` — Product Scope & Feature Boundary (in-scope/out-of-scope, rationale, MVD definition)
4. `PLAN.md` — Month-Long Build Plan (week-by-week, day-by-day breakdown)
5. `EVAL.md` — Evaluation Checklist (retrieval, grounding, multimodal, offline, security, performance, robustness, UX)
6. `VIBE.md` — Antigravity + Codex Build Instructions (phase-by-phase prompts, validation gates)
7. `ARCH.md` — Full Architecture & Deployment Diagram (text-based, Mermaid-compatible)
8. `HARDWARE.md` — Hardware Optimization Guide (AMD-specific, model manager, RAM budgeting)

---

## BUILD TOOL STRATEGY

- **Antigravity:** Backend scaffolding, API routes, React components, boilerplate structure
- **Codex:** Agent prompt engineering, CRAG logic, graph algorithms, embedding pipelines, complex state machines
- **Manual review:** Agent orchestration flow, offline proof mechanism, judge demo script

**Why the mix:** Antigravity builds skeleton fast. Codex builds brain (algorithmic logic). Neither alone handles both.

---

## CRITICAL CONSTRAINTS (Never Violate)

1. **Offline is absolute:** Core functions work with zero network. Cloud is optional, labeled, disabled by default.
2. **Citations are mandatory:** Every factual claim has [EID-xxx]. Post-processor rejects uncited claims.
3. **Abstention over hallucination:** If evidence quality < 0.6, return `INSUFFICIENT_EVIDENCE` + reason.
4. **Original files are sacred:** Read-only. All processing writes to separate artifact directory.
5. **Security by default:** Sandboxed converters, file size limits, no macro execution, quarantine on failure.

---

## JUDGE DEMO SCRIPT (Memorize This)

1. **Setup:** Show folder with manual PDF, scanned checklist, site photo, voice note. Import folder.
2. **Query 1 (Text):** "Which inspection step applies to the photographed panel?" → Show answer + manual page citation.
3. **Query 2 (Visual):** "Find diagrams similar to this photo" → ColQwen retrieves matching pages. Judge sees visual similarity search.
4. **Query 3 (Audio):** "What did the voice note say about corrosion?" → Show transcript segment with timestamp + playback.
5. **Query 4 (Unanswerable):** "What is the panel's serial number?" → System returns `INSUFFICIENT_EVIDENCE` + explains missing info.
6. **Airgap Test:** Turn off WiFi. Badge shows 🔒 OFFLINE. Repeat Query 1. Identical answer. Click "Verify Airgap" → green certificate.
7. **Conflict Demo:** Upload two docs that disagree. Query about disputed fact. System shows both sources, flags conflict, explains priority.

---

## SUCCESS METRICS

| Metric | 1-Month Target |
|--------|----------------|
| Top-5 Retrieval Recall | ≥ 90% |
| Citation Correctness | ≥ 95% |
| Grounded Answer Rate | ≥ 95% |
| Correct Abstention | ≥ 85% |
| Median Query Latency | ≤ 8s |
| Offline Success Rate | 100% |
| Import Success Rate | ≥ 97% |
| Conflict Detection Precision | ≥ 75% |

---

## CURRENT STATUS

**Phase:** Planning complete. Architecture approved. Ready for build.  
**Next step:** Begin Week 1 — Ingestion pipeline + evidence schema + native text extraction.

---

## QUESTIONS TO ASK IF RESUMING

1. What week/day of the build are we on?
2. What specific component are you stuck on?
3. Have you changed hardware or OS?
4. Are you building solo or did team size change?
5. What is the competition judging date?
