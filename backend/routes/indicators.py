# backend/routes/indicators.py
"""
Clinical indicator aggregation routes.
All queries run against patient_summary_viz — read-only.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, status

from services.indicators_service import IndicatorsService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_indicators_service(request: Request) -> IndicatorsService:
    svc = getattr(request.app.state, "indicators_service", None)
    if not svc:
        logger.error("❌ IndicatorsService not found in app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IndicatorsService not available.",
        )
    return svc


@router.get(
    "/suspected-diagnoses",
    summary="Prevalence of suspected pSBI diagnoses",
    tags=["indicators"],
    responses={
        200: {"description": "Suspected diagnosis percentages"},
        503: {"description": "IndicatorsService unavailable"},
    },
)
async def suspected_diagnoses(request: Request):
    """
    Returns three bars (0–100 %):
    - Suspected bacterial sepsis    — % of patients meeting ≥ 3 of 5 criteria groups
    - Suspected pneumonia           — % of patients meeting ≥ 2 of 5 criteria groups
    - Suspected bacterial meningitis — % of patients meeting ≥ 2 of 4 criteria groups
    """
    try:
        svc = _get_indicators_service(request)
        return await svc.psbi_suspected_diagnoses()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to compute suspected diagnoses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute suspected diagnoses: {e}",
        )


@router.get(
    "/psbi-sign-count",
    summary="Distribution of patients by number of pSBI signs/symptoms",
    tags=["indicators"],
    responses={
        200: {"description": "pSBI sign-count distribution"},
        503: {"description": "IndicatorsService unavailable"},
    },
)
async def psbi_sign_count(request: Request):
    """
    Returns one bar per distinct pSBI sign count (0 … 16).
    Each bar's `value` is the % of all patients with exactly that many signs.
    """
    try:
        svc = _get_indicators_service(request)
        return await svc.psbi_sign_count_distribution()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to compute pSBI sign-count distribution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute pSBI sign-count distribution: {e}",
        )


@router.get(
    "/infection",
    summary="Infection overview indicators",
    tags=["indicators"],
    responses={
        200: {"description": "Infection indicator percentages"},
        503: {"description": "IndicatorsService unavailable"},
    },
)
async def infection_indicators(request: Request):
    """
    Returns three bars (0–100 %):
    - Sepsis Prevalence            — % of all patients with has_sepsis = true
    - Antibiotic Treatment         — % of all patients with infection_antibiotics = true
    - Sepsis of Antibiotic Patients — % of antibiotic patients also flagged for sepsis
    """
    try:
        svc = _get_indicators_service(request)
        return await svc.infection_overview()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to compute infection indicators: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute indicators: {e}",
        )