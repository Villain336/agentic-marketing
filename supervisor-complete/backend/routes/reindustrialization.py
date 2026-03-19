"""Reindustrialization endpoints — factory sites, reshoring, workforce, energy, logistics."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/reindustrialization", tags=["Reindustrialization"])


@router.post("/sites")
async def analyze_site(payload: dict):
    """Analyze a factory site for suitability."""
    from reindustrialization import analyze_factory_site
    return await analyze_factory_site(
        payload.get("location", ""), payload.get("requirements", {}),
    )


@router.post("/reshoring")
async def reshore_analysis(payload: dict):
    """Analyze reshoring opportunity — domestic vs. overseas cost comparison."""
    from reindustrialization import reshore_supply_chain
    return await reshore_supply_chain(
        payload.get("product", ""), payload.get("current_source", "overseas"),
    )


@router.post("/workforce")
async def workforce_analysis(payload: dict):
    """Analyze workforce development needs."""
    from reindustrialization import develop_workforce
    return await develop_workforce(
        payload.get("region", ""), payload.get("roles", []),
    )


@router.get("/contracts")
async def get_gov_contracts(search_terms: str = "", naics_codes: str = ""):
    """Monitor government contract opportunities."""
    from reindustrialization import monitor_gov_contracts
    terms = [t.strip() for t in search_terms.split(",") if t.strip()] if search_terms else None
    naics = [n.strip() for n in naics_codes.split(",") if n.strip()] if naics_codes else None
    return await monitor_gov_contracts(terms, naics)


@router.get("/reshoring-metrics")
async def get_reshoring_metrics():
    """Track national reshoring progress."""
    from reindustrialization import track_reshoring_metrics
    return await track_reshoring_metrics()


@router.post("/energy")
async def energy_optimization(payload: dict):
    """Optimize factory energy consumption."""
    from reindustrialization import optimize_energy
    return await optimize_energy(
        payload.get("factory_id", ""), payload.get("optimization_target", "cost"),
    )


@router.post("/logistics")
async def logistics_optimization(payload: dict):
    """Logistics and fleet routing optimization."""
    from reindustrialization import optimize_logistics
    return await optimize_logistics(
        payload.get("origin", ""), payload.get("destination", ""),
        payload.get("cargo", {}),
    )


@router.post("/itar-check")
async def check_itar(payload: dict):
    """Check ITAR/export control compliance."""
    from reindustrialization import compliance_check_itar
    return await compliance_check_itar(
        payload.get("product_description", ""), payload.get("destination", ""),
    )


@router.post("/construction")
async def construction_plan(payload: dict):
    """Construction planning and scheduling."""
    from reindustrialization import plan_construction
    return await plan_construction(payload)


@router.post("/agriculture")
async def agriculture_automation(payload: dict):
    """Precision agriculture automation."""
    from reindustrialization import automate_agriculture
    return await automate_agriculture(
        payload.get("farm_id", ""), payload.get("operation", "status"),
    )
