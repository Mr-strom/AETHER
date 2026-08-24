#!/usr/bin/env python
"""CLI airgap verification for AETHER.

Usage:
    python verify_airgap.py

Checks:
1. Model file integrity (SHA-256 manifest comparison)
2. Network isolation (no active non-loopback interfaces with IP)
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.attestation import full_attestation


def main():
    print("=" * 60)
    print("AETHER — Airgap Verification")
    print("=" * 60)

    t0 = time.time()
    result = full_attestation()
    elapsed = time.time() - t0

    # Manifest verification
    print(f"\n🔐 Manifest Verification:")
    icon = "✅" if result["signature_valid"] else "❌"
    print(f"   {icon} Signature valid: {result['signature_valid']}")
    if result["attestation_hash"]:
        print(f"   🔑 Attestation: {result['attestation_hash']}")
    if result["timestamp"]:
        print(f"   🕐 Generated:   {result['timestamp']}")

    # File details
    if result["file_results"]:
        print(f"\n   File integrity:")
        for filename, info in result["file_results"].items():
            icon = "✅" if info["match"] else "❌"
            print(f"      {icon} {filename}: {info['actual']}")

    # Errors
    if result["errors"]:
        print(f"\n   ⚠️  Errors:")
        for err in result["errors"]:
            print(f"      - {err}")

    # Network isolation
    print(f"\n🌐 Network Isolation:")
    icon = "✅" if result["network_isolated"] else "❌"
    print(f"   {icon} Network isolated: {result['network_isolated']}")

    if result["warnings"]:
        for warn in result["warnings"]:
            print(f"   ⚠️  {warn}")

    # Summary
    print(f"\n{'=' * 60}")
    if result["all_green"]:
        print(f"🔒 ALL GREEN — System is verified offline ({elapsed:.1f}s)")
    else:
        print(f"🔓 VERIFICATION FAILED — See errors above ({elapsed:.1f}s)")
    print(f"{'=' * 60}")

    sys.exit(0 if result["all_green"] else 1)


if __name__ == "__main__":
    main()
