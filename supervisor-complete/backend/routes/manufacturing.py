"""Hardware Manufacturing — CAD, Procurement, CNC/3D Print, Production."""
from __future__ import annotations
import json

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id

router = APIRouter(prefix="/manufacturing", tags=["Manufacturing"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.post("/cad/generate")
async def generate_cad_model(request: Request):
    """Generate a 3D CAD model from natural language description."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_cad_model
    result = json.loads(await _generate_cad_model(
        payload["description"], payload.get("format", "step"),
        payload.get("parameters", ""), payload.get("material", ""),
    ))
    return result


@router.post("/cad/{model_id}/optimize")
async def optimize_cad(model_id: str, request: Request):
    """Run design optimization on a CAD model."""
    _require_auth(request)
    payload = await request.json()
    from tools import _optimize_cad_design
    result = json.loads(await _optimize_cad_design(
        model_id, payload.get("optimization_type", "topology"), payload.get("constraints", ""),
    ))
    return result


@router.post("/gcode/generate")
async def generate_gcode(request: Request):
    """Generate CNC toolpaths from a CAD model."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_gcode
    result = json.loads(await _generate_gcode(
        payload["model_id"], payload.get("machine_type", "cnc_mill"),
        payload.get("material", "aluminum_6061"), payload.get("strategy", "adaptive"),
    ))
    return result


@router.post("/print/slice")
async def slice_for_printing(request: Request):
    """Slice a 3D model for printing."""
    _require_auth(request)
    payload = await request.json()
    from tools import _slice_3d_print
    result = json.loads(await _slice_3d_print(
        payload["model_id"], payload.get("printer_type", "fdm"),
        payload.get("material", "pla"), payload.get("quality", "standard"),
    ))
    return result


@router.post("/printer/{printer_id}/command")
async def printer_command(printer_id: str, request: Request):
    """Send command to a 3D printer."""
    _require_auth(request)
    payload = await request.json()
    from tools import _control_printer
    result = json.loads(await _control_printer(printer_id, payload["command"], payload.get("file", "")))
    return result


@router.post("/cnc/{machine_id}/command")
async def cnc_command(machine_id: str, request: Request):
    """Send command to a CNC machine."""
    _require_auth(request)
    payload = await request.json()
    from tools import _control_cnc
    result = json.loads(await _control_cnc(
        machine_id, payload["command"], payload.get("gcode_file", ""), payload.get("manual_gcode", ""),
    ))
    return result


@router.post("/suppliers/search")
async def search_suppliers(request: Request):
    """Search suppliers for parts and materials."""
    _require_auth(request)
    payload = await request.json()
    from tools import _search_suppliers
    result = json.loads(await _search_suppliers(
        payload["query"], payload.get("category", "all"), payload.get("max_results", "10"),
    ))
    return result


@router.post("/bom/generate")
async def generate_bom(request: Request):
    """Generate Bill of Materials."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_bom
    result = json.loads(await _generate_bom(
        payload["model_id"], payload.get("quantity", "1"), payload.get("include_alternatives", "true"),
    ))
    return result


@router.post("/rfq/send")
async def send_rfq(request: Request):
    """Send Request for Quotes to suppliers."""
    _require_auth(request)
    payload = await request.json()
    from tools import _send_rfq
    result = json.loads(await _send_rfq(
        json.dumps(payload.get("suppliers", [])), json.dumps(payload.get("parts", [])),
        payload.get("quantity", "100"), payload.get("deadline_days", "7"),
    ))
    return result


@router.post("/inspect")
async def inspect_part(request: Request):
    """Vision-based quality inspection of manufactured parts."""
    _require_auth(request)
    payload = await request.json()
    from tools import _inspect_part_vision
    result = json.loads(await _inspect_part_vision(
        payload.get("image_b64", ""), payload.get("model_id", ""), payload.get("inspection_type", "visual"),
    ))
    return result


@router.post("/pcb/generate")
async def generate_pcb(request: Request):
    """Generate PCB layout from schematic."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_pcb_layout
    result = json.loads(await _generate_pcb_layout(
        payload["schematic"], payload.get("board_size", ""), payload.get("layers", "2"), payload.get("components", ""),
    ))
    return result


@router.get("/print-farm/status")
async def print_farm_status(request: Request):
    """Get print farm status."""
    _require_auth(request)
    from tools import _manage_print_farm
    result = json.loads(await _manage_print_farm("status"))
    return result


@router.post("/production/plan")
async def create_production_plan(request: Request):
    """Create manufacturing production plan."""
    _require_auth(request)
    payload = await request.json()
    from tools import _production_plan
    result = json.loads(await _production_plan(
        payload["product_id"], payload.get("quantity", "100"),
        payload.get("deadline", ""), payload.get("process", "cnc"),
    ))
    return result


@router.post("/drawing/generate")
async def generate_drawing(request: Request):
    """Generate 2D manufacturing drawings from 3D model."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_technical_drawing
    result = json.loads(await _generate_technical_drawing(
        payload["model_id"], payload.get("views", "standard"), payload.get("include_gdt", "true"),
    ))
    return result
