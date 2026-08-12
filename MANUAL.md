# AETHER Development Manual & Architecture Log

## Phase 1 Summary

Phase 1 establishes the complete Model Download Engine, Text-Only Multimodal Ingestion Pipeline, BGE-M3 FAISS Indexing Service, and Agentic Query Reasoning Pipeline for **AETHER** — an offline, CPU-primary multimodal evidence RAG system.

### Core Modules Implemented

1. **Model Download Engine (`setup_models.py`)**:
   - Automated downloader and integrity validator for GGUF models stored in `./models`.
   - IBM Granite 4 Tiny H (`granite-4.0-h-tiny-Q4_K_M.gguf`, ~1.5 GB) for Query Planning and Evidence Validation.
   - Qwen2.5 3B Instruct (`Qwen2.5-3B-Instruct-Q4_K_M.gguf`, ~2.6 GB) for Grounded Answer Synthesis.
   - Dynamic SHA-256 verification via Hugging Face LFS metadata APIs.

2. **Ingestion Pipeline (`backend/services/ingest/`)**:
   - `schema.py`: Standardized `IngestChunk` dataclass (`source_path`, `chunk_index`, `text`, `modality`, `page_number`, `char_count`, `embedding_id`, `bbox`, `extra`).
   - `text.py`: Extractor for `.txt`, `.md`, `.rst`, `.log` files with UTF-8/Latin-1 fallback, 2048-character (~512 token) sliding window chunking, 50-char overlap, and newline boundary splitting.
   - `pdf.py`: PyMuPDF (`fitz`) page extractor with font-size and bold heading heuristics (`## ` conversion), bounding box (`bbox`) capture, and long page re-chunking.
   - `docx.py`: `python-docx` extractor preserving heading levels (`#`, `##`, `###`) and converting Word tables to GitHub-Flavoured Markdown tables.
   - `table.py`: `pandas` & `openpyxl` extractor for `.csv`, `.xlsx`, `.xls` files generating pipe-delimited row evidence strings (`Column: Value | Column: Value`).
   - `router.py`: `IngestRouter` using MIME-type detection and file extension fallbacks for clean error handling (`UnsupportedFileTypeError`).

3. **Indexing Services (`backend/services/index/`)**:
   - `embeddings.py`: Singleton `EmbeddingService` for BAAI/bge-m3 dense 1024-dim vectors with batching (`batch_size=32`), thread-safety, and empty-string sentinel substitution.
   - `faiss_index.py`: `FAISSIndexService` wrapping `IndexFlatIP` (inner product / cosine similarity) for 1024-dim vectors with FAISS-ID to `EvidenceChunk` ID mapping and disk persistence (`.faiss` + `.ids`).

4. **Query Reasoning Pipeline (`backend/services/retrieve/` & `backend/routers/query.py`)**:
   - `model_manager.py`: `SmartModelManager` managing resident (Granite 4 Tiny H) and non-resident (Qwen2.5-3B) model swapping within the 14.3 GB RAM budget.
   - `planner.py`: `QueryPlannerService` using Granite 4 Tiny H to generate structured `QueryPlan` JSON (`primary_modality`, `sub_queries`, `filters`, `requires_calculation`).
   - `retriever.py`: `HybridRetrieverService` executing BGE-M3 query embedding, FAISS dense search (top-20), BM25 sparse search fallback, BGE-Reranker cross-encoder scoring, and DB evidence resolution.
   - `synthesizer.py`: `AnswerSynthesizerService` using Qwen2.5-3B under Grounding Contract rules (`[EID-xxx]` citations, `INSUFFICIENT_EVIDENCE` fallback, `Unknowns:` section).
   - `validators.py`: `validate_citations` verifying cited `[EID-xxx]` tags against retrieved evidence IDs, detecting uncited claims, and parsing `Unknowns:` sections.
   - `query.py`: `POST /api/query` FastAPI endpoint orchestrating planning, retrieval, synthesis, validation, and latency logging.

---

## Architectural Hurdles

1. **Model Memory Footprint & RAM Budgeting**:
   - *Problem*: Concurrent execution of multiple 3B+ parameter models alongside FAISS indices risks exceeding available system RAM (16 GB total, 14.3 GB budget).
   - *Resolution*: Implemented `SmartModelManager` with a strict resident vs. non-resident model swapping policy. Granite 4 Tiny H (~1.5 GB) remains resident for fast planning, while Qwen2.5-3B (~2.6 GB) is loaded on demand during synthesis and immediately unloaded (`gc.collect()`).

2. **Sliding Window Chunking Boundary Bug**:
   - *Problem*: In `backend/services/ingest/text.py`, when text length was smaller than or equal to `chunk_size`, calculating `next_start = end - overlap` resulted in `next_start <= start`, which advanced `start` by 1 character per iteration instead of terminating, generating duplicate single-character offset chunks.
   - *Resolution*: Added explicit termination check `if end >= text_len: break` inside `_split_into_chunks`.

3. **Optional Binary Dependency Import Guards**:
   - *Problem*: Direct top-level imports of PyMuPDF (`fitz`), `python-docx`, `pandas`, `faiss`, or `pydantic_settings` caused module import crashes when running lightweight commands or tests in environments lacking specific optional C/binary packages.
   - *Resolution*: Refactored imports across extractors, indexers, and router modules to use `try ... except ImportError` guards at module load time, deferring strict package assertions to execution time inside method calls.

4. **Dynamic Hugging Face SHA-256 Resolution**:
   - *Problem*: Hardcoding expected SHA-256 checksums for GGUF model files leads to brittle scripts when upstream repository commits or quantization files update on Hugging Face Hub.
   - *Resolution*: Integrated dynamic LFS metadata lookups in `setup_models.py` using `huggingface_hub.HfApi` and public REST API endpoints to fetch authoritative LFS object SHA-256 hashes at runtime.

5. **Tabular Context Loss in Vector Search**:
   - *Problem*: Standard text chunkers strip structural table headers, producing detached cell values that perform poorly in dense vector search.
   - *Resolution*: Implemented row-by-row pipe-delimited formatting (`Header1: Val1 | Header2: Val2`) in `TableIngester`, ensuring every row chunk retains explicit column headers.

---

## AI Action Log

- **Scaffolded Architecture**: Engineered the complete backend layout (`FastAPI`, `SQLAlchemy 2.0`, `aiosqlite`, `Pydantic v2`) and React 18 / Vite / Tailwind dark-mode 3-panel frontend workspace.
- **Ingestion Pipeline**: Implemented multi-format document parsers for `.txt`, `.md`, `.pdf`, `.docx`, `.csv`, `.xlsx`, `.xls` with unified `IngestChunk` output.
- **Vector Indexing Engine**: Built 1024-dim BGE-M3 embedding service and FAISS `IndexFlatIP` vector index service with integer ID mapping and file persistence.
- **Agentic Reasoning Engine**: Implemented `SmartModelManager`, `QueryPlannerService`, `HybridRetrieverService`, `AnswerSynthesizerService`, citation post-processor `validate_citations`, and `POST /api/query` router.
- **Model Downloader**: Developed `setup_models.py` supporting automatic Hugging Face model downloads, LFS checksum validation, disk space checks, and system RAM diagnostics.
- **Testing & Verification Suite**: Developed end-to-end verification scripts (`smoke_test.py`, `test_ingestion_manual.py`, `test_end_to_end.py`) and 92 unit test items in `backend/tests/`.
- **Repository Security & Documentation**: Audited workspace files and generated `.gitignore`, `.env.example`, `MANUAL.md`, and `README.md`.
