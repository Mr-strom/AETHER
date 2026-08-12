# Project "either" - Phase 1: Model Download & Ingestion Pipeline

**AETHER** is an offline, CPU-primary multimodal evidence Retrieval-Augmented Generation (RAG) system designed for privacy-preserving, localized document analysis and factual answer synthesis.

---

## System Flow

### 1. Model Download Engine (`setup_models.py`)
The download engine checks system hardware (RAM and free disk space) and downloads verified GGUF weights into `./models`:
- **Planner & Validator**: `ibm-granite/granite-4.0-h-tiny-GGUF` (`granite-4.0-h-tiny-Q4_K_M.gguf`, ~1.5 GB) — Always resident for query planning and validation.
- **Synthesizer**: `bartowski/Qwen2.5-3B-Instruct-GGUF` (`Qwen2.5-3B-Instruct-Q4_K_M.gguf`, ~2.6 GB) — Swapped on demand for grounded answer generation.
- **Embeddings & Reranking**: `BAAI/bge-m3` (1024-dim dense vectors) and `BAAI/bge-reranker-base`.
- Integrity is validated using dynamic Hugging Face LFS SHA-256 object hashes.

```
[Hugging Face Hub] ──> [setup_models.py] ──SHA-256 Check──> [./models/*.gguf]
```

### 2. Ingestion & Vector Indexing Pipeline
The ingestion pipeline processes multi-format documents into standardized evidence units and builds a FAISS vector index:

```
                  ┌───────────────┐
                  │ Source Files  │
                  │(.txt,.md,.pdf,│
                  │ .docx,.csv,   │
                  │ .xlsx)        │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ IngestRouter  │
                  └───────┬───────┘
                          │
       ┌──────────┬───────┼───────┬──────────┐
       ▼          ▼       ▼       ▼          ▼
   [TextIngester][PDF] [Docx]  [Table]   [Schema]
       │          │       │       │          │
       └──────────┴───────┼───────┴──────────┘
                          │
                          ▼
                   [IngestChunk]
                          │
                          ▼
            [BGE-M3 EmbeddingService] (1024-dim)
                          │
                          ▼
             [FAISSIndexService] (IndexFlatIP)
                          │
                          ▼
                  [./data/index.faiss]
```

1. **Routing**: `IngestRouter` inspects file extension and MIME type to dispatch files to the appropriate extractor.
2. **Extraction**:
   - `TextIngester`: Character sliding window (~512 tokens / 2048 chars, 50-char overlap) with encoding fallbacks (UTF-8 / Latin-1).
   - `PDFIngester`: PyMuPDF page extraction with header formatting heuristics (`## `) and bounding box (`bbox`) capture.
   - `DocxIngester`: Heading level preservation (`#`, `##`) and table rendering to Markdown tables.
   - `TableIngester`: CSV and multi-sheet XLSX row extraction formatted as pipe-delimited evidence (`Col: Val | Col: Val`).
3. **Embedding**: `EmbeddingService` generates 1024-dimensional normalized dense vectors using BGE-M3 in batches of 32.
4. **FAISS Indexing**: `FAISSIndexService` adds vectors to an `IndexFlatIP` index and maintains EvidenceChunk ID mappings saved to disk (`index.faiss` and `index.ids`).

---

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- Git

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Mr-strom/AETHER.git
   cd AETHER
   ```

2. **Create and activate a virtual environment:**
   - **Windows:**
     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Python dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements-text-only.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

---

## Usage

### 1. Download & Verify Model Stack
Trigger the automated model download engine:
```bash
python setup_models.py
```

### 2. Run Model Smoke Test
Verify memory budget and model loading:
```bash
python smoke_test.py
```

### 3. Run Ingestion & Indexing Pipeline Test
Generate demo documents and execute manual ingestion and FAISS vector index verification:
```bash
python generate_demo_files.py
python test_ingestion_manual.py
```

### 4. Execute End-to-End Query Reasoning Pipeline
Run an end-to-end test query through Planning (Granite) $\rightarrow$ Retrieval (FAISS + BGE-M3) $\rightarrow$ Synthesis (Qwen) $\rightarrow$ Citation Validation:
```bash
python test_end_to_end.py
```

### 5. Launch FastAPI Backend Server
Start the production API server:
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```
Health endpoint is available at: `http://localhost:8000/api/health`

### 6. Launch React Frontend App
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.
