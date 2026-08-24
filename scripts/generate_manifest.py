#!/usr/bin/env python
"""Generate SHA-256 manifest for AETHER model files.

Run once at install time:
    python generate_manifest.py

Generates ./manifest.json containing SHA-256 hashes of all .gguf model
files in ./models/. This manifest is used by the airgap verification
system to prove model integrity without network access.
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.attestation import generate_manifest


def main():
    print("=" * 60)
    print("AETHER — Model Manifest Generator")
    print("=" * 60)

    models_dir = Path("./models")
    manifest_path = Path("./manifest.json")

    if not models_dir.exists():
        print(f"\n❌ Models directory not found: {models_dir.absolute()}")
        sys.exit(1)

    gguf_files = list(models_dir.glob("*.gguf"))
    if not gguf_files:
        print(f"\n❌ No .gguf files found in {models_dir.absolute()}")
        sys.exit(1)

    print(f"\nModels directory: {models_dir.absolute()}")
    print(f"Found {len(gguf_files)} model file(s):\n")

    for f in sorted(gguf_files):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"   📦 {f.name:<50} ({size_mb:.0f} MB)")

    print(f"\nComputing SHA-256 hashes (this may take a minute for large models)...")
    t0 = time.time()

    try:
        manifest = generate_manifest(models_dir, manifest_path)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    elapsed = time.time() - t0

    print(f"\n✅ Manifest generated in {elapsed:.1f}s")
    print(f"   📄 Saved to: {manifest_path.absolute()}")
    print(f"   🔑 Attestation: {manifest['attestation_hash'][:32]}...")
    print(f"   🕐 Timestamp:   {manifest['timestamp']}")

    print(f"\nFile hashes:")
    for filename, sha in manifest["files"].items():
        print(f"   {filename}: {sha[:32]}...")

    print(f"\n✅ Done. Run 'python verify_airgap.py' to verify.")


if __name__ == "__main__":
    main()
