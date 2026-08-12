# AETHER: text-only, CPU-only model setup

This setup downloads only the two GGUF language models plus the BGE embedding and reranking models. It does not install or download vision, audio, Whisper, ColQwen, CUDA, or Vulkan components.

Use Python 3.11 in a fresh virtual environment, then install the pinned text-only stack:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-text-only.txt
python setup_models.py
```

The script installs `llama-cpp-python` with its normal CPU-only build path, downloads the GGUF files to `./models`, obtains each file's SHA-256 from the publisher's Hugging Face LFS metadata, and prints the expected and calculated hashes before accepting the file. BGE models are verified by loading them through `sentence-transformers`; their weights use the Hugging Face cache (normally under `%USERPROFILE%\.cache\huggingface`).

Useful commands:

```powershell
# Check RAM, AVX2, CPU threads, and model-drive space without downloading.
python setup_models.py --report-only

# If dependencies were installed already.
python setup_models.py --skip-llama-install

# Store GGUF files elsewhere.
python setup_models.py --models-dir D:\AETHER-models
```

For a 16 GB system, the all-model estimate is about 10.8 GiB, staying below the 14 GiB model budget. Actual use varies with llama.cpp context size, batch size, and concurrent requests; use a modest context size and do not keep both GGUF models serving large requests simultaneously if Windows memory pressure is high.
