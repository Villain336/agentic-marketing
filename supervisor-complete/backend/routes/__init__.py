"""
Route registry — imports and exposes all APIRouter instances.

Usage in main.py:
    from routes import all_routers
    for router in all_routers:
        app.include_router(router)
"""
from routes.health import router as health_router
from routes.websocket import router as websocket_router
from routes.agents import router as agents_router
from routes.campaigns import router as campaigns_router
from routes.onboarding import router as onboarding_router
from routes.webhooks import router as webhooks_router
from routes.approvals import router as approvals_router
from routes.settings import router as settings_router
from routes.scoring import router as scoring_router
from routes.budget import router as budget_router
from routes.campaign_templates import router as templates_router
from routes.tenants import router as tenants_router
from routes.revshare import router as revshare_router
from routes.skills import router as skills_router
from routes.marketplace_routes import router as marketplace_router
from routes.whatsapp_routes import router as whatsapp_router
from routes.replanner_routes import router as replanner_router
from routes.deployment import router as deployment_router
from routes.privacy_routes import router as privacy_router
from routes.finetuning import router as finetuning_router
from routes.research import router as research_router
from routes.design import router as design_router
from routes.browser import router as browser_router
from routes.manufacturing import router as manufacturing_router
from routes.security import router as security_router
from routes.nvidia import router as nvidia_router
from routes.aws import router as aws_router
from routes.reindustrialization import router as reindustrialization_router
from routes.integrations import router as integrations_router

all_routers = [
    health_router,
    websocket_router,
    agents_router,
    campaigns_router,
    onboarding_router,
    webhooks_router,
    approvals_router,
    settings_router,
    scoring_router,
    budget_router,
    templates_router,
    tenants_router,
    revshare_router,
    skills_router,
    marketplace_router,
    whatsapp_router,
    replanner_router,
    deployment_router,
    privacy_router,
    finetuning_router,
    research_router,
    design_router,
    browser_router,
    manufacturing_router,
    security_router,
    nvidia_router,
    aws_router,
    reindustrialization_router,
    integrations_router,
]
