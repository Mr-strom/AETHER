"""API endpoints for system status and model manager management."""

from fastapi import APIRouter, Depends
from backend.app.config import Settings
from backend.app.dependencies import get_settings
from backend.schemas.system import SystemStatusResponse
from backend.services.attestation import full_attestation

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    settings: Settings = Depends(get_settings),
) -> SystemStatusResponse:
    """Get comprehensive system status, RAM budget, and model info."""
    return SystemStatusResponse(
        status="ok",
        version=settings.VERSION,
        models_loaded=[],
        ram_budget_mb=float(settings.RAM_BUDGET_MB),
        ram_usage_mb=0.0,
        gpu_layers=settings.GPU_LAYERS,
        gpu_available=False,
        active_sources_count=0,
        total_evidence_chunks=0,
    )


@router.get("/verify-airgap")
async def verify_airgap(
    settings: Settings = Depends(get_settings),
):
    """Verify airgap: model manifest integrity + network isolation.

    Returns JSON with:
        - all_green: bool — True if manifest valid AND network isolated
        - signature_valid: bool
        - network_isolated: bool
        - errors: list of error strings
        - warnings: list of warning strings
    """
    result = full_attestation(
        models_dir=settings.MODELS_DIR,
    )
    return result

