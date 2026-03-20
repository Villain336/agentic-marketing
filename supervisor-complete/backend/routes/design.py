"""Design view / canvas endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from designview import design_view
from auth import get_user_id

router = APIRouter(prefix="/design", tags=["Design"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.post("/canvas")
async def create_design_canvas(request: Request):
    """Create a new design canvas."""
    _require_auth(request)
    body = await request.json()
    canvas = design_view.create_canvas(
        campaign_id=body["campaign_id"],
        name=body.get("name", "Untitled"),
        template_id=body.get("template_id", ""),
        width=body.get("width", 1440),
        height=body.get("height", 900),
    )
    return canvas.model_dump()


@router.get("/canvas/{canvas_id}")
async def get_design_canvas(canvas_id: str, request: Request):
    """Get a design canvas."""
    _require_auth(request)
    canvas = design_view.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(404, "Canvas not found")
    return canvas.model_dump()


@router.get("/canvases/{campaign_id}")
async def list_design_canvases(campaign_id: str, request: Request):
    """List canvases for a campaign."""
    _require_auth(request)
    canvases = design_view.list_canvases(campaign_id)
    return {"canvases": [c.model_dump() for c in canvases]}


@router.post("/canvas/{canvas_id}/component")
async def add_design_component(canvas_id: str, request: Request):
    """Add a component from the library to a canvas."""
    _require_auth(request)
    body = await request.json()
    element = design_view.add_component(
        canvas_id, body["component"],
        x=body.get("x", 0), y=body.get("y", 0),
        overrides=body.get("overrides"),
    )
    if not element:
        raise HTTPException(400, "Canvas or component not found")
    return element.model_dump()


@router.patch("/canvas/{canvas_id}/element/{element_id}")
async def update_design_element(canvas_id: str, element_id: str, request: Request):
    """Update a design element's properties or styles."""
    _require_auth(request)
    body = await request.json()
    element = design_view.update_element(canvas_id, element_id, body)
    if not element:
        raise HTTPException(404, "Canvas or element not found")
    return element.model_dump()


@router.delete("/canvas/{canvas_id}/element/{element_id}")
async def delete_design_element(canvas_id: str, element_id: str, request: Request):
    """Delete a design element."""
    _require_auth(request)
    success = design_view.delete_element(canvas_id, element_id)
    if not success:
        raise HTTPException(404, "Canvas not found")
    return {"deleted": True}


@router.get("/canvas/{canvas_id}/export/html")
async def export_design_html(canvas_id: str, request: Request, responsive: bool = True):
    """Export canvas as production HTML."""
    _require_auth(request)
    html = design_view.export_html(canvas_id, responsive)
    if not html:
        raise HTTPException(404, "Canvas not found")
    return {"html": html}


@router.get("/canvas/{canvas_id}/export/react")
async def export_design_react(canvas_id: str, request: Request):
    """Export canvas as a React component."""
    _require_auth(request)
    react = design_view.export_react(canvas_id)
    if not react:
        raise HTTPException(404, "Canvas not found")
    return {"react": react}


@router.get("/templates")
async def list_design_templates(category: str = ""):
    """List available design templates (public)."""
    templates = design_view.get_templates(category)
    return {"templates": [t.model_dump() for t in templates]}


@router.get("/components")
async def list_design_components():
    """List the component library (public)."""
    return {"components": design_view.get_component_library()}


@router.get("/canvas/{canvas_id}/history")
async def get_design_history(canvas_id: str, request: Request):
    """Get edit history for undo/redo."""
    _require_auth(request)
    return {"history": design_view.get_edit_history(canvas_id)}
