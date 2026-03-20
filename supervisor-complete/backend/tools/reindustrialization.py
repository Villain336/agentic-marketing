"""
Factory site analysis, robot fleet, reshoring, energy, workforce, and logistics.
"""

from __future__ import annotations

import json

from tools.registry import _to_json


async def _analyze_factory_site(location: str, requirements: str = "{}") -> str:
    try:
        from reindustrialization import analyze_factory_site
        reqs = json.loads(requirements) if isinstance(requirements, str) else requirements
        result = await analyze_factory_site(location, reqs)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "location": location})



async def _manage_robot_fleet(fleet_id: str, action: str = "status", robot_id: str = "", task: str = "") -> str:
    try:
        from reindustrialization import manage_robot_fleet
        result = await manage_robot_fleet(fleet_id, action, robot_id=robot_id, task=task)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "fleet_id": fleet_id})



async def _reshore_supply_chain(product: str, current_source: str = "overseas") -> str:
    try:
        from reindustrialization import reshore_supply_chain
        result = await reshore_supply_chain(product, current_source)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "product": product})



async def _operate_digital_twin(twin_id: str, operation: str = "status", scenario: str = "{}") -> str:
    try:
        from reindustrialization import operate_digital_twin
        sc = json.loads(scenario) if isinstance(scenario, str) else scenario
        result = await operate_digital_twin(twin_id, operation, scenario=sc)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "twin_id": twin_id})



async def _optimize_energy(factory_id: str, optimization_target: str = "cost") -> str:
    try:
        from reindustrialization import optimize_energy
        result = await optimize_energy(factory_id, optimization_target)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "factory_id": factory_id})



async def _develop_workforce(region: str, roles: str = "") -> str:
    try:
        from reindustrialization import develop_workforce
        role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else None
        result = await develop_workforce(region, role_list)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "region": region})



async def _monitor_gov_contracts(search_terms: str = "", naics_codes: str = "") -> str:
    try:
        from reindustrialization import monitor_gov_contracts
        terms = [t.strip() for t in search_terms.split(",") if t.strip()] if search_terms else None
        naics = [n.strip() for n in naics_codes.split(",") if n.strip()] if naics_codes else None
        result = await monitor_gov_contracts(terms, naics)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _automate_agriculture(farm_id: str, operation: str = "status") -> str:
    try:
        from reindustrialization import automate_agriculture
        result = await automate_agriculture(farm_id, operation)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "farm_id": farm_id})



async def _plan_construction(project_name: str, project_type: str = "factory") -> str:
    try:
        from reindustrialization import plan_construction
        result = await plan_construction({"name": project_name, "type": project_type})
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "project_name": project_name})



async def _optimize_logistics(origin: str, destination: str, cargo_type: str = "") -> str:
    try:
        from reindustrialization import optimize_logistics
        result = await optimize_logistics(origin, destination, {"type": cargo_type} if cargo_type else None)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "origin": origin, "destination": destination})



async def _track_reshoring_metrics() -> str:
    try:
        from reindustrialization import track_reshoring_metrics
        result = await track_reshoring_metrics()
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _compliance_check_itar(product_description: str, destination: str = "") -> str:
    try:
        from reindustrialization import compliance_check_itar
        result = await compliance_check_itar(product_description, destination)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "product_description": product_description})




def register_reindustrialization_tools(registry):
    """Register all reindustrialization tools with the given registry."""
    from models import ToolParameter

    registry.register("analyze_factory_site", "Analyze a factory site for suitability — labor, taxes, energy, supply chain.",
        [ToolParameter(name="location", description="Location to analyze (city, state)"),
         ToolParameter(name="requirements", description="Requirements JSON", required=False)],
        _analyze_factory_site, "reindustrialization")

    registry.register("manage_robot_fleet", "Manage industrial robot fleet — status, maintenance, task assignment.",
        [ToolParameter(name="fleet_id", description="Fleet identifier"),
         ToolParameter(name="action", description="Action: status, schedule_maintenance, assign_task", required=False),
         ToolParameter(name="robot_id", description="Specific robot ID", required=False),
         ToolParameter(name="task", description="Task to assign", required=False)],
        _manage_robot_fleet, "reindustrialization")

    registry.register("reshore_supply_chain", "Analyze reshoring opportunity — domestic vs. overseas cost comparison.",
        [ToolParameter(name="product", description="Product or component to reshore"),
         ToolParameter(name="current_source", description="Current source: overseas, china, mexico, etc.", required=False)],
        _reshore_supply_chain, "reindustrialization")

    registry.register("operate_digital_twin", "Operate a factory digital twin — status, simulate, optimize.",
        [ToolParameter(name="twin_id", description="Digital twin ID"),
         ToolParameter(name="operation", description="Operation: status, simulate, optimize", required=False),
         ToolParameter(name="scenario", description="Scenario config JSON", required=False)],
        _operate_digital_twin, "reindustrialization")

    registry.register("optimize_energy", "Optimize factory energy consumption and costs.",
        [ToolParameter(name="factory_id", description="Factory identifier"),
         ToolParameter(name="optimization_target", description="Target: cost, carbon, reliability", required=False)],
        _optimize_energy, "reindustrialization")

    registry.register("develop_workforce", "Analyze workforce development needs — skills gaps, training programs.",
        [ToolParameter(name="region", description="Region to analyze"),
         ToolParameter(name="roles", description="Comma-separated roles to analyze", required=False)],
        _develop_workforce, "reindustrialization")

    registry.register("monitor_gov_contracts", "Monitor SAM.gov for government contract opportunities.",
        [ToolParameter(name="search_terms", description="Comma-separated search terms", required=False),
         ToolParameter(name="naics_codes", description="Comma-separated NAICS codes", required=False)],
        _monitor_gov_contracts, "reindustrialization")

    registry.register("automate_agriculture", "Precision agriculture automation — soil analysis, crop planning, equipment coordination.",
        [ToolParameter(name="farm_id", description="Farm identifier"),
         ToolParameter(name="operation", description="Operation: status, irrigate, harvest, plant", required=False)],
        _automate_agriculture, "reindustrialization")

    registry.register("plan_construction", "Construction planning — scheduling, costing, OSHA compliance.",
        [ToolParameter(name="project_name", description="Project name"),
         ToolParameter(name="project_type", description="Type: factory, warehouse, office, modular", required=False)],
        _plan_construction, "reindustrialization")

    registry.register("optimize_logistics", "Logistics optimization — fleet routing, warehouse, last-mile delivery.",
        [ToolParameter(name="origin", description="Origin location"),
         ToolParameter(name="destination", description="Destination location"),
         ToolParameter(name="cargo_type", description="Cargo type", required=False)],
        _optimize_logistics, "reindustrialization")

    registry.register("track_reshoring_metrics", "Track national reshoring progress and metrics.",
        [], _track_reshoring_metrics, "reindustrialization")

    registry.register("compliance_check_itar", "Check ITAR/export control compliance for a product.",
        [ToolParameter(name="product_description", description="Product description"),
         ToolParameter(name="destination", description="Export destination country/region", required=False)],
        _compliance_check_itar, "reindustrialization")

