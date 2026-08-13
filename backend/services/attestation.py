"""Airgap attestation service.

Provides cryptographic manifest generation/verification for model files
and network isolation checks to prove the system is fully offline.
Uses only standard library (hashlib) + psutil for network checks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_MODELS_DIR = Path("./models")
MANIFEST_PATH = Path("./manifest.json")


def _sha256_file(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file.

    Args:
        file_path: Path to the file.
        chunk_size: Read buffer size in bytes.

    Returns:
        Lowercase hex digest string.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(
    models_dir: Path = DEFAULT_MODELS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> Dict[str, Any]:
    """Compute SHA-256 hashes of all .gguf model files and save manifest.

    Args:
        models_dir: Directory containing model files.
        manifest_path: Where to write the manifest JSON.

    Returns:
        The generated manifest dict.
    """
    models_dir = Path(models_dir)
    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found: {models_dir}")

    gguf_files = sorted(models_dir.glob("*.gguf"))
    if not gguf_files:
        raise FileNotFoundError(f"No .gguf files found in {models_dir}")

    file_hashes: Dict[str, str] = {}
    for f in gguf_files:
        logger.info("Hashing %s (%d MB)...", f.name, f.stat().st_size // (1024 * 1024))
        file_hashes[f.name] = _sha256_file(f)

    # Compute attestation hash over all individual hashes (deterministic ordering)
    combined = "".join(f"{k}:{v}" for k, v in sorted(file_hashes.items()))
    attestation_hash = hashlib.sha256(combined.encode()).hexdigest()

    timestamp = datetime.now(timezone.utc).isoformat()

    manifest = {
        "files": file_hashes,
        "attestation_hash": attestation_hash,
        "timestamp": timestamp,
        "signature": attestation_hash[:16],  # Simplified signature (first 16 chars)
        "models_dir": str(models_dir.resolve()),
    }

    manifest_path = Path(manifest_path)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        "Manifest generated: %d files, attestation=%s",
        len(file_hashes),
        attestation_hash[:16],
    )
    return manifest


def verify_manifest(
    models_dir: Path = DEFAULT_MODELS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> Dict[str, Any]:
    """Recompute model file hashes and compare against saved manifest.

    Args:
        models_dir: Directory containing model files.
        manifest_path: Path to the manifest.json file.

    Returns:
        Dict with verification results:
            - signature_valid: bool
            - attestation_hash: str
            - timestamp: str (from manifest)
            - file_results: dict of {filename: {"expected": ..., "actual": ..., "match": bool}}
            - errors: list of error strings
    """
    manifest_path = Path(manifest_path)
    models_dir = Path(models_dir)

    result: Dict[str, Any] = {
        "signature_valid": False,
        "attestation_hash": "",
        "timestamp": "",
        "file_results": {},
        "errors": [],
    }

    # Load manifest
    if not manifest_path.exists():
        result["errors"].append(f"Manifest not found: {manifest_path}")
        return result

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result["errors"].append(f"Failed to read manifest: {e}")
        return result

    result["timestamp"] = manifest.get("timestamp", "")
    expected_files = manifest.get("files", {})

    if not expected_files:
        result["errors"].append("Manifest contains no file entries.")
        return result

    # Verify each file
    file_results: Dict[str, Dict[str, Any]] = {}
    all_match = True

    for filename, expected_hash in expected_files.items():
        file_path = models_dir / filename
        if not file_path.exists():
            file_results[filename] = {
                "expected": expected_hash[:16] + "...",
                "actual": "FILE_MISSING",
                "match": False,
            }
            all_match = False
            result["errors"].append(f"Model file missing: {filename}")
            continue

        actual_hash = _sha256_file(file_path)
        match = actual_hash == expected_hash

        file_results[filename] = {
            "expected": expected_hash[:16] + "...",
            "actual": actual_hash[:16] + "...",
            "match": match,
        }

        if not match:
            all_match = False
            result["errors"].append(f"Hash mismatch for {filename}")

    # Recompute attestation hash
    combined = "".join(f"{k}:{v}" for k, v in sorted(expected_files.items()))
    expected_attestation = hashlib.sha256(combined.encode()).hexdigest()

    result["file_results"] = file_results
    result["attestation_hash"] = expected_attestation[:16] + "..."
    result["signature_valid"] = all_match and len(result["errors"]) == 0

    return result


def check_network_isolation() -> Dict[str, Any]:
    """Check that all non-loopback network interfaces are down or have no IP.

    Uses psutil to enumerate network interfaces. Only loopback ("lo" on Linux,
    "Loopback" on Windows) should have addresses. All others must be down
    or have no assigned IP address.

    Returns:
        Dict with:
            - network_isolated: bool
            - interfaces: dict of {name: {status, addresses}}
            - warnings: list of warning strings
    """
    result: Dict[str, Any] = {
        "network_isolated": True,
        "interfaces": {},
        "warnings": [],
    }

    try:
        import psutil
    except ImportError:
        result["warnings"].append("psutil not installed — cannot verify network isolation.")
        result["network_isolated"] = False
        return result

    # Get interface addresses
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        iface_lower = iface_name.lower()
        is_loopback = (
            iface_lower in ("lo", "loopback pseudo-interface 1")
            or "loopback" in iface_lower
        )

        iface_info: Dict[str, Any] = {
            "is_loopback": is_loopback,
            "is_up": False,
            "ipv4_addresses": [],
        }

        # Check if interface is up
        if iface_name in stats:
            iface_info["is_up"] = stats[iface_name].isup

        # Collect IPv4 addresses
        for addr in addr_list:
            if addr.family.name in ("AF_INET",) or getattr(addr.family, "value", 0) == 2:
                iface_info["ipv4_addresses"].append(addr.address)

        result["interfaces"][iface_name] = iface_info

        # Check for non-loopback interfaces with real IPs that are UP
        if not is_loopback and iface_info["is_up"]:
            real_ips = [
                ip for ip in iface_info["ipv4_addresses"]
                if ip and ip != "127.0.0.1" and not ip.startswith("169.254.")
            ]
            if real_ips:
                result["network_isolated"] = False
                result["warnings"].append(
                    f"Interface '{iface_name}' is UP with IP(s): {real_ips}"
                )

    return result


def full_attestation(
    models_dir: Path = DEFAULT_MODELS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> Dict[str, Any]:
    """Run full airgap attestation: manifest verification + network isolation check.

    Args:
        models_dir: Directory containing model files.
        manifest_path: Path to the manifest.json file.

    Returns:
        Combined dict with all_green boolean and component results.
    """
    manifest_result = verify_manifest(models_dir, manifest_path)
    network_result = check_network_isolation()

    all_green = (
        manifest_result["signature_valid"]
        and network_result["network_isolated"]
    )

    return {
        "all_green": all_green,
        "signature_valid": manifest_result["signature_valid"],
        "attestation_hash": manifest_result["attestation_hash"],
        "timestamp": manifest_result["timestamp"],
        "network_isolated": network_result["network_isolated"],
        "file_results": manifest_result["file_results"],
        "network_interfaces": network_result["interfaces"],
        "errors": manifest_result["errors"],
        "warnings": network_result["warnings"],
    }
