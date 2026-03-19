"""White-label tenant management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from whitelabel import tenant_manager
from auth import get_user_id
from store import store

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("")
async def create_tenant(request: Request):
    """Create a new white-label tenant."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    try:
        tenant = tenant_manager.create_tenant(
            name=body["name"],
            slug=body["slug"],
            owner_user_id=user_id,
            brand_name=body.get("brand_name", ""),
            brand_logo_url=body.get("brand_logo_url", ""),
            brand_color_primary=body.get("brand_color_primary", "#000000"),
            brand_color_accent=body.get("brand_color_accent", "#0066FF"),
            custom_domain=body.get("custom_domain", ""),
            plan=body.get("plan", "pro"),
        )
        return tenant.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_tenants(request: Request):
    """List tenants owned by the authenticated user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    all_tenants = tenant_manager.list_tenants()
    # Filter to only show tenants owned by the authenticated user
    return {"tenants": [t for t in all_tenants
                        if (t.get("owner_user_id") if isinstance(t, dict) else getattr(t, "owner_user_id", "")) == user_id]}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, request: Request):
    """Get tenant configuration."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if getattr(tenant, "owner_user_id", "") != user_id:
        raise HTTPException(403, "Not your tenant")
    return tenant.model_dump()


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, request: Request):
    """Update tenant configuration."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if getattr(tenant, "owner_user_id", "") != user_id:
        raise HTTPException(403, "Not your tenant")
    body = await request.json()
    body.pop("owner_user_id", None)  # Prevent IDOR — owner cannot be changed
    tenant = tenant_manager.update_tenant(tenant_id, **body)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant.model_dump()


@router.get("/{tenant_id}/limits")
async def check_tenant_limits(tenant_id: str, request: Request):
    """Check a tenant's usage against their plan limits."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if getattr(tenant, "owner_user_id", "") != user_id:
        raise HTTPException(403, "Not your tenant")

    tenant_campaigns = store.campaign_count(tenant.owner_user_id)
    return tenant_manager.check_limits(tenant, tenant_campaigns, 0)


@router.get("/by-slug/{slug}")
async def get_tenant_by_slug(slug: str):
    """Look up tenant by slug (used for custom domain routing). Public — returns only branding."""
    tenant = tenant_manager.get_tenant_by_slug(slug)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return {
        "id": tenant.id,
        "brand_name": tenant.brand_name or tenant.name,
        "brand_logo_url": tenant.brand_logo_url,
        "brand_color_primary": tenant.brand_color_primary,
        "brand_color_accent": tenant.brand_color_accent,
    }
