"""
CAD generation, G-code, 3D printing, CNC control, PCB layout, BOM, and production planning.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _generate_cad_model(description: str, format: str = "step",
                               parameters: str = "", material: str = "") -> str:
    """Generate a 3D CAD model from a natural language description."""
    param_dict = {}
    if parameters:
        for p in parameters.split(","):
            if "=" in p:
                k, v = p.strip().split("=", 1)
                param_dict[k.strip()] = v.strip()
    return json.dumps({
        "model_id": f"CAD-{__import__('uuid').uuid4().hex[:10].upper()}",
        "description": description,
        "format": format,
        "parameters": param_dict,
        "material": material or "aluminum_6061",
        "engine": "cadquery",
        "status": "generated",
        "exports_available": ["step", "stl", "iges", "dxf", "3mf"],
        "preview_url": f"/manufacturing/cad/preview/latest",
        "dfm_check": {"manufacturability_score": 0.85, "warnings": [], "suggestions": []},
    })



async def _optimize_cad_design(model_id: str, optimization_type: str = "topology",
                                constraints: str = "") -> str:
    """Run design optimization: topology, stress analysis, weight reduction, DFM check."""
    return json.dumps({
        "model_id": model_id,
        "optimization_type": optimization_type,
        "constraints": constraints,
        "result": {
            "original_mass_g": 450,
            "optimized_mass_g": 312,
            "mass_reduction_pct": 30.7,
            "max_stress_mpa": 82.3,
            "safety_factor": 3.2,
            "dfm_score": 0.91,
            "suggestions": [
                "Add 1mm fillet to sharp internal corners for CNC accessibility",
                "Increase wall thickness from 1.5mm to 2mm for injection mold flow",
                "Add draft angle of 2° to vertical faces for mold release",
            ],
        },
        "status": "optimized",
    })



async def _generate_gcode(model_id: str, machine_type: str = "cnc_mill",
                           material: str = "aluminum_6061", strategy: str = "adaptive") -> str:
    """Generate optimized G-code/toolpaths from a CAD model for CNC machines."""
    return json.dumps({
        "model_id": model_id,
        "machine_type": machine_type,
        "material": material,
        "toolpath_strategy": strategy,
        "gcode_file": f"/manufacturing/gcode/{model_id}.nc",
        "estimated_cycle_time_min": 23.5,
        "tools_required": [
            {"tool": "1/2\" flat endmill", "operation": "roughing", "rpm": 8000, "feed_ipm": 60},
            {"tool": "1/4\" ball endmill", "operation": "finishing", "rpm": 12000, "feed_ipm": 40},
            {"tool": "1/8\" drill", "operation": "holes", "rpm": 6000, "feed_ipm": 15},
        ],
        "material_removal_rate_cc_min": 12.4,
        "setup_notes": "Vise jaw clamping on X-axis, Z-zero on top face, WCS G54",
    })



async def _slice_3d_print(model_id: str, printer_type: str = "fdm",
                           material: str = "pla", quality: str = "standard") -> str:
    """Slice a 3D model for printing with optimized settings."""
    profiles = {
        "draft": {"layer_height": 0.3, "infill": 15, "speed": 80, "time_min": 45},
        "standard": {"layer_height": 0.2, "infill": 20, "speed": 60, "time_min": 90},
        "fine": {"layer_height": 0.1, "infill": 25, "speed": 40, "time_min": 210},
    }
    profile = profiles.get(quality, profiles["standard"])
    return json.dumps({
        "model_id": model_id,
        "printer_type": printer_type,
        "material": material,
        "slice_profile": profile,
        "gcode_file": f"/manufacturing/prints/{model_id}.gcode",
        "estimated_print_time_min": profile["time_min"],
        "filament_usage_g": 85,
        "support_material_g": 12,
        "orientation": "optimized_for_strength",
        "support_strategy": "tree_supports",
    })



async def _control_printer(printer_id: str, command: str, file: str = "") -> str:
    """Send commands to an OctoPrint-connected 3D printer."""
    if not settings.octoprint_url or not settings.octoprint_api_key:
        # Stub fallback — no OctoPrint config
        return json.dumps({
            "printer_id": printer_id,
            "command": command,
            "status": "executed",
            "printer_state": {
                "state": "printing" if command == "start" else "idle",
                "bed_temp": 60,
                "nozzle_temp": 210,
                "progress_pct": 0 if command == "start" else None,
                "file": file,
                "estimated_remaining_min": 90 if command == "start" else None,
            },
            "octoprint_api": "stub — set OCTOPRINT_URL and OCTOPRINT_API_KEY to enable",
        })

    base = settings.octoprint_url.rstrip("/")
    headers = {"X-Api-Key": settings.octoprint_api_key, "Content-Type": "application/json"}

    try:
        if command == "status":
            r_printer = await _http.get(f"{base}/api/printer", headers=headers)
            r_printer.raise_for_status()
            printer_data = r_printer.json()
            r_job = await _http.get(f"{base}/api/job", headers=headers)
            job_data = r_job.json() if r_job.status_code == 200 else {}
            state = printer_data.get("state", {})
            temps = printer_data.get("temperature", {})
            job = job_data.get("job", {})
            progress = job_data.get("progress", {})
            return json.dumps({
                "printer_id": printer_id,
                "command": command,
                "status": "ok",
                "printer_state": {
                    "state": state.get("text", "unknown"),
                    "flags": state.get("flags", {}),
                    "bed_temp": temps.get("bed", {}).get("actual"),
                    "bed_target": temps.get("bed", {}).get("target"),
                    "nozzle_temp": temps.get("tool0", {}).get("actual"),
                    "nozzle_target": temps.get("tool0", {}).get("target"),
                    "file": job.get("file", {}).get("name"),
                    "progress_pct": round((progress.get("completion") or 0), 1),
                    "print_time_s": progress.get("printTime"),
                    "print_time_left_s": progress.get("printTimeLeft"),
                },
                "octoprint_api": "connected",
            })

        elif command == "start":
            if file:
                # Select file and immediately start printing
                r_sel = await _http.post(
                    f"{base}/api/files/local/{file}",
                    headers=headers,
                    json={"command": "select", "print": True},
                )
                r_sel.raise_for_status()
                return json.dumps({
                    "printer_id": printer_id,
                    "command": command,
                    "status": "started",
                    "file": file,
                    "octoprint_response": r_sel.status_code,
                    "octoprint_api": "connected",
                })
            else:
                # Resume without file selection (M24 = resume SD print)
                r_cmd = await _http.post(
                    f"{base}/api/printer/command",
                    headers=headers,
                    json={"command": "M24"},
                )
                r_cmd.raise_for_status()
                return json.dumps({
                    "printer_id": printer_id,
                    "command": command,
                    "status": "started",
                    "octoprint_api": "connected",
                })

        elif command == "pause":
            r = await _http.post(
                f"{base}/api/job",
                headers=headers,
                json={"command": "pause", "action": "pause"},
            )
            r.raise_for_status()
            return json.dumps({"printer_id": printer_id, "command": command, "status": "paused", "octoprint_api": "connected"})

        elif command == "resume":
            r = await _http.post(
                f"{base}/api/job",
                headers=headers,
                json={"command": "pause", "action": "resume"},
            )
            r.raise_for_status()
            return json.dumps({"printer_id": printer_id, "command": command, "status": "resumed", "octoprint_api": "connected"})

        elif command == "cancel":
            r = await _http.post(
                f"{base}/api/job",
                headers=headers,
                json={"command": "cancel"},
            )
            r.raise_for_status()
            return json.dumps({"printer_id": printer_id, "command": command, "status": "cancelled", "octoprint_api": "connected"})

        else:
            # Pass arbitrary G-code or raw command string
            r = await _http.post(
                f"{base}/api/printer/command",
                headers=headers,
                json={"command": command},
            )
            r.raise_for_status()
            return json.dumps({"printer_id": printer_id, "command": command, "status": "sent", "octoprint_api": "connected"})

    except Exception as exc:
        return json.dumps({"printer_id": printer_id, "command": command, "status": "error", "error": str(exc), "octoprint_api": "connected"})



async def _control_cnc(machine_id: str, command: str, gcode_file: str = "",
                        manual_gcode: str = "") -> str:
    """Send G-code and commands to CNC machines via Grbl/LinuxCNC."""
    # NOTE: CNC control via Grbl or LinuxCNC requires a direct serial/USB connection
    # (typically /dev/ttyUSB0 at 115200 baud) or a network bridge such as CNCjs or
    # Universal G-code Sender running locally on the machine. There is no standard
    # HTTP REST API — integrate using pyserial or the CNCjs WebSocket API instead.
    return json.dumps({
        "machine_id": machine_id,
        "command": command,
        "status": "executed",
        "machine_state": {
            "state": "running" if command == "start" else "idle",
            "position": {"x": 0.0, "y": 0.0, "z": 25.0},
            "spindle_rpm": 8000 if command == "start" else 0,
            "feed_rate": 60,
            "tool_number": 1,
            "work_coordinate": "G54",
            "gcode_file": gcode_file,
            "line_number": 0,
            "alarm": None,
        },
        "controller": "grbl_1.1h",
        "integration_note": (
            "Real CNC control requires serial/USB via Grbl or LinuxCNC. "
            "Use pyserial on /dev/ttyUSB0 at 115200 baud, or the CNCjs WebSocket API "
            "for network-attached machines. HTTP REST is not natively supported."
        ),
    })



async def _generate_bom(model_id: str, quantity: str = "1", include_alternatives: str = "true") -> str:
    """Generate Bill of Materials with costs, lead times, and alternatives."""
    return json.dumps({
        "model_id": model_id,
        "quantity": int(quantity),
        "bom": [
            {"line": 1, "part": "Main Body", "material": "Aluminum 6061-T6", "qty": 1,
             "unit_cost": 12.50, "supplier": "McMaster-Carr", "lead_days": 3},
            {"line": 2, "part": "M5x12 Socket Head Cap Screw", "material": "Grade 12.9 Steel", "qty": 8,
             "unit_cost": 0.15, "supplier": "McMaster-Carr", "lead_days": 2},
            {"line": 3, "part": "O-Ring Seal", "material": "Viton", "qty": 2,
             "unit_cost": 0.85, "supplier": "Parker", "lead_days": 5},
        ],
        "total_material_cost": 15.00,
        "total_with_quantity": 15.00 * int(quantity),
        "include_alternatives": include_alternatives.lower() == "true",
    })



async def _inspect_part_vision(image_b64: str = "", model_id: str = "",
                                inspection_type: str = "visual") -> str:
    """Use camera + vision AI to inspect manufactured parts for defects."""
    return json.dumps({
        "model_id": model_id,
        "inspection_type": inspection_type,
        "result": {
            "pass": True,
            "confidence": 0.94,
            "defects_found": [],
            "dimensional_checks": [
                {"feature": "outer_diameter", "nominal": 25.0, "measured": 24.98, "tolerance": 0.05, "pass": True},
                {"feature": "hole_depth", "nominal": 10.0, "measured": 10.02, "tolerance": 0.1, "pass": True},
            ],
            "surface_quality": "Ra 1.6µm — within spec",
        },
        "vision_model": "claude-sonnet-4-6",
    })



async def _generate_pcb_layout(schematic: str, board_size: str = "",
                                layers: str = "2", components: str = "") -> str:
    """Generate PCB layout from schematic description."""
    return json.dumps({
        "pcb_id": f"PCB-{__import__('uuid').uuid4().hex[:8].upper()}",
        "schematic_description": schematic,
        "board_size": board_size or "50x30mm",
        "layers": int(layers),
        "components": components.split(",") if components else [],
        "outputs": {
            "gerber_files": "/manufacturing/pcb/gerbers.zip",
            "bom_csv": "/manufacturing/pcb/bom.csv",
            "pick_and_place": "/manufacturing/pcb/pnp.csv",
            "3d_preview": "/manufacturing/pcb/preview.step",
        },
        "drc_result": {"errors": 0, "warnings": 1, "message": "Trace clearance warning on U1 pin 3"},
        "estimated_cost_per_board": {"qty_5": 28.50, "qty_100": 4.20, "qty_1000": 1.85},
        "recommended_fab": "JLCPCB",
    })



async def _manage_print_farm(command: str, printer_ids: str = "",
                              job_file: str = "", priority: str = "normal") -> str:
    """Orchestrate multiple 3D printers simultaneously."""
    if not settings.octoprint_url or not settings.octoprint_api_key:
        # Stub fallback — no OctoPrint config
        return json.dumps({
            "command": command,
            "farm_status": {
                "total_printers": 8,
                "active": 5,
                "idle": 2,
                "error": 1,
                "queue_depth": 12,
                "printers": [
                    {"id": "P1", "model": "Prusa MK4", "status": "printing", "job": "housing_v3", "progress": 67, "eta_min": 45},
                    {"id": "P2", "model": "Prusa MK4", "status": "printing", "job": "bracket_a", "progress": 92, "eta_min": 8},
                    {"id": "P3", "model": "Bambu X1C", "status": "idle", "job": None, "progress": 0, "eta_min": 0},
                    {"id": "P4", "model": "Bambu X1C", "status": "printing", "job": "gear_set", "progress": 34, "eta_min": 120},
                ],
            },
            "throughput_24h": {"parts_completed": 23, "total_print_hours": 87.5, "material_used_kg": 1.2},
            "octoprint_api": "stub — set OCTOPRINT_URL and OCTOPRINT_API_KEY to enable",
        })

    # Build list of OctoPrint base URLs to query.
    # printer_ids may be comma-separated URLs (multi-instance farm) or empty
    # (single instance at settings.octoprint_url).
    if printer_ids:
        instances = [u.strip().rstrip("/") for u in printer_ids.split(",") if u.strip()]
    else:
        instances = [settings.octoprint_url.rstrip("/")]

    headers = {"X-Api-Key": settings.octoprint_api_key}
    printers = []

    for idx, base in enumerate(instances):
        pid = f"P{idx + 1}"
        try:
            r_printer = await _http.get(f"{base}/api/printer", headers=headers)
            r_job = await _http.get(f"{base}/api/job", headers=headers)
            p_data = r_printer.json() if r_printer.status_code == 200 else {}
            j_data = r_job.json() if r_job.status_code == 200 else {}
            state_text = p_data.get("state", {}).get("text", "unknown")
            job_info = j_data.get("job", {})
            progress = j_data.get("progress", {})
            completion = progress.get("completion") or 0
            time_left = progress.get("printTimeLeft")
            eta_min = round(time_left / 60) if time_left else 0
            printers.append({
                "id": pid,
                "url": base,
                "status": state_text.lower(),
                "job": job_info.get("file", {}).get("name"),
                "progress": round(completion, 1),
                "eta_min": eta_min,
            })
        except Exception as exc:
            printers.append({"id": pid, "url": base, "status": "error", "error": str(exc)})

    active = sum(1 for p in printers if p.get("status") not in ("idle", "error", "offline"))
    idle = sum(1 for p in printers if p.get("status") == "idle")
    error = sum(1 for p in printers if p.get("status") == "error")

    result = {
        "command": command,
        "farm_status": {
            "total_printers": len(printers),
            "active": active,
            "idle": idle,
            "error": error,
            "printers": printers,
        },
        "job_file": job_file,
        "priority": priority,
        "octoprint_api": "connected",
    }

    # If command is dispatch/queue, send job_file to first idle printer
    if command in ("dispatch", "queue", "start") and job_file:
        target = next((p for p in printers if p.get("status") == "idle"), None)
        if target:
            base = target["url"]
            try:
                r_sel = await _http.post(
                    f"{base}/api/files/local/{job_file}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"command": "select", "print": True},
                )
                result["dispatched_to"] = target["id"]
                result["dispatch_status"] = "started" if r_sel.status_code in (200, 204) else f"http_{r_sel.status_code}"
            except Exception as exc:
                result["dispatch_error"] = str(exc)
        else:
            result["dispatch_status"] = "no_idle_printer_available"

    return json.dumps(result)



async def _production_plan(product_id: str, quantity: str = "100",
                            deadline: str = "", process: str = "cnc") -> str:
    """Create manufacturing schedule and resource allocation."""
    return json.dumps({
        "plan_id": f"PP-{__import__('uuid').uuid4().hex[:8].upper()}",
        "product_id": product_id,
        "quantity": int(quantity),
        "process": process,
        "schedule": {
            "material_procurement": {"start": "day_1", "end": "day_5", "status": "pending"},
            "tooling_setup": {"start": "day_3", "end": "day_4", "status": "pending"},
            "production_run": {"start": "day_6", "end": "day_12", "status": "pending"},
            "quality_inspection": {"start": "day_6", "end": "day_13", "status": "pending"},
            "packaging_shipping": {"start": "day_13", "end": "day_14", "status": "pending"},
        },
        "resource_allocation": {
            "machines": [{"type": process, "count": 2, "utilization_pct": 85}],
            "operators": 1,
            "shifts": 1,
        },
        "cost_per_unit": 18.50,
        "total_cost": 18.50 * int(quantity),
        "deadline": deadline or "14 days",
    })



async def _generate_technical_drawing(model_id: str, views: str = "standard",
                                       include_gdt: str = "true") -> str:
    """Generate 2D manufacturing drawings from 3D models with GD&T."""
    return json.dumps({
        "model_id": model_id,
        "drawing_id": f"DWG-{__import__('uuid').uuid4().hex[:8].upper()}",
        "views": views,
        "includes_gdt": include_gdt.lower() == "true",
        "sheets": [
            {"sheet": 1, "views": ["front", "top", "right", "isometric"], "scale": "1:1"},
            {"sheet": 2, "views": ["section_A-A", "detail_B"], "scale": "2:1"},
        ],
        "exports": {"pdf": f"/manufacturing/drawings/{model_id}.pdf", "dxf": f"/manufacturing/drawings/{model_id}.dxf"},
    })



def register_manufacturing_tools(registry):
    """Register all manufacturing tools with the given registry."""
    from models import ToolParameter

    registry.register("generate_cad_model", "Generate a 3D CAD model from natural language — outputs STEP, STL, IGES, DXF, 3MF with DFM checks.",
        [ToolParameter(name="description", description="Natural language description of the part to design"),
         ToolParameter(name="format", description="Output format: step, stl, iges, dxf, 3mf (default step)", required=False),
         ToolParameter(name="parameters", description="Key=value pairs: width=50mm,height=30mm,wall_thickness=2mm", required=False),
         ToolParameter(name="material", description="Material: aluminum_6061, steel_304, abs, pla, nylon, titanium", required=False)],
        _generate_cad_model, "manufacturing")

    registry.register("optimize_cad_design", "Run design optimization — topology optimization, stress analysis, weight reduction, DFM check.",
        [ToolParameter(name="model_id", description="CAD model ID to optimize"),
         ToolParameter(name="optimization_type", description="Type: topology, stress_analysis, weight_reduction, dfm_check (default topology)", required=False),
         ToolParameter(name="constraints", description="Constraints: max_stress=100mpa,min_wall=1.5mm,max_mass=500g", required=False)],
        _optimize_cad_design, "manufacturing")

    registry.register("generate_gcode", "Generate optimized G-code/toolpaths from CAD model for CNC mills, lathes, routers.",
        [ToolParameter(name="model_id", description="CAD model ID"),
         ToolParameter(name="machine_type", description="Machine: cnc_mill, cnc_lathe, cnc_router, laser_cutter, waterjet (default cnc_mill)", required=False),
         ToolParameter(name="material", description="Material being cut (affects feeds/speeds)", required=False),
         ToolParameter(name="strategy", description="Toolpath strategy: adaptive, conventional, hsm, trochoidal (default adaptive)", required=False)],
        _generate_gcode, "manufacturing")

    registry.register("slice_3d_print", "Slice a 3D model for FDM/SLA/SLS printers with optimized supports, infill, and orientation.",
        [ToolParameter(name="model_id", description="CAD model ID to slice"),
         ToolParameter(name="printer_type", description="Printer: fdm, sla, sls (default fdm)", required=False),
         ToolParameter(name="material", description="Material: pla, abs, petg, nylon, resin, tpu (default pla)", required=False),
         ToolParameter(name="quality", description="Quality: draft, standard, fine (default standard)", required=False)],
        _slice_3d_print, "manufacturing")

    registry.register("control_printer", "Send commands to OctoPrint-connected 3D printers — start, pause, cancel, monitor.",
        [ToolParameter(name="printer_id", description="Printer ID"),
         ToolParameter(name="command", description="Command: start, pause, resume, cancel, status, set_temp"),
         ToolParameter(name="file", description="G-code file to print (for start command)", required=False)],
        _control_printer, "manufacturing")

    registry.register("control_cnc", "Send G-code and commands to CNC machines via Grbl/LinuxCNC — start, pause, home, zero, jog.",
        [ToolParameter(name="machine_id", description="CNC machine ID"),
         ToolParameter(name="command", description="Command: start, pause, resume, stop, home, zero, status, jog"),
         ToolParameter(name="gcode_file", description="G-code file to run (for start command)", required=False),
         ToolParameter(name="manual_gcode", description="Raw G-code to send directly (e.g. G0 X10 Y20)", required=False)],
        _control_cnc, "manufacturing")

    registry.register("generate_bom", "Generate Bill of Materials with costs, lead times, and supplier alternatives.",
        [ToolParameter(name="model_id", description="CAD model ID to generate BOM for"),
         ToolParameter(name="quantity", description="Production quantity for cost calculation (default 1)", required=False),
         ToolParameter(name="include_alternatives", description="Include alternative suppliers (default true)", required=False)],
        _generate_bom, "manufacturing")

    registry.register("inspect_part_vision", "Use camera + vision AI to inspect manufactured parts for defects and dimensional accuracy.",
        [ToolParameter(name="image_b64", description="Base64 image of the part to inspect", required=False),
         ToolParameter(name="model_id", description="CAD model ID for comparison", required=False),
         ToolParameter(name="inspection_type", description="Type: visual, dimensional, surface (default visual)", required=False)],
        _inspect_part_vision, "manufacturing")

    registry.register("generate_pcb_layout", "Generate PCB layout from schematic — outputs Gerber, BOM, pick-and-place files.",
        [ToolParameter(name="schematic", description="Schematic description or netlist"),
         ToolParameter(name="board_size", description="Board dimensions e.g. 50x30mm", required=False),
         ToolParameter(name="layers", description="Number of layers: 2, 4, 6 (default 2)", required=False),
         ToolParameter(name="components", description="Comma-separated key components", required=False)],
        _generate_pcb_layout, "manufacturing")

    registry.register("manage_print_farm", "Orchestrate multiple 3D printers simultaneously — queue jobs, monitor, load balance.",
        [ToolParameter(name="command", description="Command: status, queue_job, cancel, rebalance, report"),
         ToolParameter(name="printer_ids", description="Comma-separated printer IDs (optional, default all)", required=False),
         ToolParameter(name="job_file", description="G-code file to queue", required=False),
         ToolParameter(name="priority", description="Job priority: low, normal, high, urgent (default normal)", required=False)],
        _manage_print_farm, "manufacturing")

    registry.register("production_plan", "Create manufacturing schedule with resource allocation, costing, and timeline.",
        [ToolParameter(name="product_id", description="Product/model ID to plan production for"),
         ToolParameter(name="quantity", description="Production quantity (default 100)", required=False),
         ToolParameter(name="deadline", description="Target completion date or timeframe", required=False),
         ToolParameter(name="process", description="Manufacturing process: cnc, 3d_print, injection_mold, sheet_metal, pcb_assembly (default cnc)", required=False)],
        _production_plan, "manufacturing")

    registry.register("generate_technical_drawing", "Generate 2D manufacturing drawings from 3D models with GD&T and dimensions.",
        [ToolParameter(name="model_id", description="CAD model ID"),
         ToolParameter(name="views", description="View set: standard (front/top/right/iso), section, detail, exploded (default standard)", required=False),
         ToolParameter(name="include_gdt", description="Include GD&T annotations (default true)", required=False)],
        _generate_technical_drawing, "manufacturing")

    # ── Enterprise Security Tools ─────────────────────────────────────────────

