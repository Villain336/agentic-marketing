"""Reindustrialization endpoints — factory sites, reshoring, workforce, energy, logistics."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id

router = APIRouter(prefix="/reindustrialization", tags=["Reindustrialization"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.post("/sites")
async def analyze_site(request: Request):
    """Analyze a factory site for suitability."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import analyze_factory_site
    return await analyze_factory_site(
        payload.get("location", ""), payload.get("requirements", {}),
    )


@router.post("/reshoring")
async def reshore_analysis(request: Request):
    """Analyze reshoring opportunity — domestic vs. overseas cost comparison."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import reshore_supply_chain
    return await reshore_supply_chain(
        payload.get("product", ""), payload.get("current_source", "overseas"),
    )


@router.post("/workforce")
async def workforce_analysis(request: Request):
    """Analyze workforce development needs."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import develop_workforce
    return await develop_workforce(
        payload.get("region", ""), payload.get("roles", []),
    )


@router.get("/contracts")
async def get_gov_contracts(request: Request, search_terms: str = "", naics_codes: str = ""):
    """Monitor government contract opportunities."""
    _require_auth(request)
    from reindustrialization import monitor_gov_contracts
    terms = [t.strip() for t in search_terms.split(",") if t.strip()] if search_terms else None
    naics = [n.strip() for n in naics_codes.split(",") if n.strip()] if naics_codes else None
    return await monitor_gov_contracts(terms, naics)


@router.get("/reshoring-metrics")
async def get_reshoring_metrics(request: Request):
    """Track national reshoring progress."""
    _require_auth(request)
    from reindustrialization import track_reshoring_metrics
    return await track_reshoring_metrics()


@router.post("/energy")
async def energy_optimization(request: Request):
    """Optimize factory energy consumption."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import optimize_energy
    return await optimize_energy(
        payload.get("factory_id", ""), payload.get("optimization_target", "cost"),
    )


@router.post("/logistics")
async def logistics_optimization(request: Request):
    """Logistics and fleet routing optimization."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import optimize_logistics
    return await optimize_logistics(
        payload.get("origin", ""), payload.get("destination", ""),
        payload.get("cargo", {}),
    )


@router.post("/itar-check")
async def check_itar(request: Request):
    """Check ITAR/export control compliance."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import compliance_check_itar
    return await compliance_check_itar(
        payload.get("product_description", ""), payload.get("destination", ""),
    )


@router.post("/construction")
async def construction_plan(request: Request):
    """Construction planning and scheduling."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import plan_construction
    return await plan_construction(payload)


@router.post("/agriculture")
async def agriculture_automation(request: Request):
    """Precision agriculture automation."""
    _require_auth(request)
    payload = await request.json()
    from reindustrialization import automate_agriculture
    return await automate_agriculture(
        payload.get("farm_id", ""), payload.get("operation", "status"),
    )
