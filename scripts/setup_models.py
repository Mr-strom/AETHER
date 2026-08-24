#!/usr/bin/env python3
"""Download and verify AETHER's CPU-only, text-only RAG model stack.

This script deliberately does not download vision, audio, or GPU model assets.
Run from the AETHER repository root:
    python setup_models.py
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil


MODELS_DIR = Path(__file__).resolve().parent / "models"
GIB = 1024 ** 3


@dataclass(frozen=True)
class GGUFModel:
    name: str
    repo_id: str
    filename: str
    purpose: str
    estimated_disk_gib: float
    estimated_ram_gib: float


GGUF_MODELS = (
    GGUFModel(
        name="Planner + Validator",
        repo_id="ibm-granite/granite-4.0-h-tiny-GGUF",
        filename="granite-4.0-h-tiny-Q4_K_M.gguf",
        purpose="Fast query planning and evidence validation",
        estimated_disk_gib=1.5,
        estimated_ram_gib=2.0,
    ),
    # NEW — CORRECT MODEL, CORRECT REPO, FITS YOUR RAM
    GGUFModel(
        name="Synthesizer",
        repo_id="bartowski/Qwen2.5-3B-Instruct-GGUF",
        filename="Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        purpose="Grounded answer generation with citations",
        estimated_disk_gib=2.6,
        estimated_ram_gib=2.5,
    ),
)

EMBEDDING_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-base"
ESTIMATED_ALL_LOADED_RAM_GIB = 10.8  # GGUF weights/KV cache + embedding and reranker models.


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hf_expected_sha256(repo_id: str, filename: str) -> str:
    """Read the publisher's LFS SHA-256 from Hugging Face metadata.

    The LFS object ID is a SHA-256 of the exact file, so it is authoritative for
    this revision and avoids brittle, stale hashes embedded in this script.
    """
    from huggingface_hub import HfApi

    info = HfApi().model_info(repo_id, files_metadata=True)
    for sibling in info.siblings:
        if sibling.rfilename != filename:
            continue
        lfs = getattr(sibling, "lfs", None)
        expected = getattr(lfs, "sha256", None) or getattr(lfs, "oid", None)
        if expected:
            return expected.removeprefix("sha256:").lower()
    raise RuntimeError(f"Hugging Face metadata has no SHA-256 for {repo_id}/{filename}")


def requests_expected_sha256(repo_id: str, filename: str) -> str:
    """Read the same LFS SHA-256 from the public Hugging Face API."""
    import requests

    response = requests.get(f"https://huggingface.co/api/models/{repo_id}?blobs=true", timeout=30)
    response.raise_for_status()
    for sibling in response.json().get("siblings", []):
        if sibling.get("rfilename") == filename:
            lfs = sibling.get("lfs") or {}
            expected = lfs.get("sha256") or lfs.get("oid")
            if expected:
                return expected.removeprefix("sha256:").lower()
    raise RuntimeError(f"Hugging Face API has no SHA-256 for {repo_id}/{filename}")


def expected_sha256(repo_id: str, filename: str) -> str:
    """Prefer huggingface_hub metadata, with an HTTP API fallback."""
    try:
        return hf_expected_sha256(repo_id, filename)
    except ImportError:
        print("huggingface_hub unavailable; reading hash with requests fallback.")
        return requests_expected_sha256(repo_id, filename)


def download_with_huggingface_hub(model: GGUFModel, destination: Path) -> Path:
    from huggingface_hub import hf_hub_download

    downloaded = hf_hub_download(
        repo_id=model.repo_id,
        filename=model.filename,
        local_dir=str(destination),
    )
    return Path(downloaded)


def download_with_requests(model: GGUFModel, destination: Path) -> Path:
    """Fallback downloader for environments without huggingface_hub installed."""
    import requests
    from tqdm import tqdm

    destination.mkdir(parents=True, exist_ok=True)
    output = destination / model.filename
    url = f"https://huggingface.co/{model.repo_id}/resolve/main/{model.filename}"
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with output.open("wb") as handle, tqdm(
            total=total, unit="B", unit_scale=True, desc=model.filename
        ) as progress:
            for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    progress.update(len(chunk))
    return output


def download_and_verify(model: GGUFModel, destination: Path) -> Path:
    """Download a GGUF and verify it against the repository's published SHA-256."""
    print(f"\n{model.name}: {model.repo_id}/{model.filename}")
    expected = expected_sha256(model.repo_id, model.filename)
    target = destination / model.filename
    if target.exists():
        print(f"Using existing file: {target}")
        downloaded = target
    else:
        try:
            downloaded = download_with_huggingface_hub(model, destination)
        except ImportError:
            print("huggingface_hub unavailable; using requests fallback.")
            downloaded = download_with_requests(model, destination)

    actual = sha256_file(downloaded)
    print(f"  Expected SHA-256: {expected}")
    print(f"  Actual SHA-256:   {actual}")
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {downloaded}. Delete the file and retry.")
    print("  Verification: PASS")
    return downloaded


def install_llama_cpp() -> None:
    """Install the standard CPU-only wheel/build; no CUDA or Vulkan flags are used."""
    print("\nInstalling llama-cpp-python with the CPU-only backend...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "llama-cpp-python", "--no-cache-dir"],
        check=True,
    )


def verify_sentence_transformers() -> None:
    """Download/load the text embedding and cross-encoder reranking models."""
    from sentence_transformers import CrossEncoder, SentenceTransformer

    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    embedder = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=False)
    vector = embedder.encode("AETHER verifies grounded answers.", normalize_embeddings=True)
    print(f"  Embedding verification: PASS ({len(vector)} dimensions)")

    print(f"Loading reranker model: {RERANKER_MODEL}")
    reranker = CrossEncoder(RERANKER_MODEL, trust_remote_code=False)
    score = float(reranker.predict([("What does AETHER use?", "AETHER uses text retrieval.")])[0])
    print(f"  Reranker verification: PASS (test score {score:.4f})")


def avx2_supported() -> Optional[bool]:
    """Return AVX2 support where the OS exposes it; None means inconclusive."""
    if os.name == "nt":
        PF_AVX2_INSTRUCTIONS_AVAILABLE = 40
        return bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(PF_AVX2_INSTRUCTIONS_AVAILABLE))
    try:
        flags = Path("/proc/cpuinfo").read_text(encoding="utf-8").lower()
        return "avx2" in flags
    except OSError:
        return None


def cpu_model() -> str:
    """Return the OS-reported processor marketing name where possible."""
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    return platform.processor().strip() or "Unknown CPU"


def print_hardware_report(models_dir: Path) -> None:
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(models_dir)
    avx2 = avx2_supported()
    avx2_text = "YES" if avx2 else "NO" if avx2 is False else "UNKNOWN"
    cpu_name = cpu_model()

    print("\n" + "=" * 64)
    print("AETHER CPU-ONLY TEXT RAG HARDWARE COMPATIBILITY REPORT")
    print("=" * 64)
    print(f"CPU model:             {cpu_name}")
    print(f"CPU logical threads:   {os.cpu_count() or 'Unknown'}")
    print(f"Total RAM:             {memory.total / GIB:.2f} GiB")
    print(f"Available RAM:         {memory.available / GIB:.2f} GiB")
    print(f"AVX2 supported:        {avx2_text} (required/recommended by llama.cpp CPU builds)")
    print(f"Models directory:      {models_dir}")
    print(f"Free disk space:       {disk.free / GIB:.2f} GiB")
    print(f"Estimated GGUF disk:   {sum(m.estimated_disk_gib for m in GGUF_MODELS):.1f} GiB")
    print(f"Estimated all-model RAM usage: {ESTIMATED_ALL_LOADED_RAM_GIB:.1f} GiB")
    fits = memory.total / GIB >= 16 and ESTIMATED_ALL_LOADED_RAM_GIB <= 14
    print(f"14 GiB model budget:   {'PASS' if fits else 'CHECK CURRENT MACHINE'}")
    if memory.available / GIB < ESTIMATED_ALL_LOADED_RAM_GIB:
        print("WARNING: Current available RAM is below the estimated all-model footprint.")
    if avx2 is False:
        print("WARNING: AVX2 was not detected; llama.cpp CPU performance/compatibility may be limited.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR, help="GGUF destination (default: ./models)")
    parser.add_argument("--skip-llama-install", action="store_true", help="Do not run pip install llama-cpp-python --no-cache-dir")
    parser.add_argument("--skip-transformer-check", action="store_true", help="Do not download/load BGE models")
    parser.add_argument("--report-only", action="store_true", help="Only print the hardware report")
    args = parser.parse_args()
    models_dir = args.models_dir.resolve()
    models_dir.mkdir(parents=True, exist_ok=True)

    print_hardware_report(models_dir)
    if args.report_only:
        return 0
    if not args.skip_llama_install:
        install_llama_cpp()
    for model in GGUF_MODELS:
        download_and_verify(model, models_dir)
    if not args.skip_transformer_check:
        verify_sentence_transformers()
    print("\nAETHER text-only model setup completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nSETUP FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
