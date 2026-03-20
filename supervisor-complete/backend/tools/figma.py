"""
Figma file, component, style, asset export, and design token extraction.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _figma_get_file(file_key: str, components_only: bool = False) -> str:
    """Get Figma file data — pages, frames, components, styles."""
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True, "note": "Configure Figma API key to access design files directly."})
    try:
        url = f"https://api.figma.com/v1/files/{file_key}"
        if components_only:
            url += "?depth=1"
        resp = await _http.get(url, headers={"X-FIGMA-TOKEN": settings.figma_api_key})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "file_name": data.get("name", ""),
                "last_modified": data.get("lastModified", ""),
                "version": data.get("version", ""),
                "pages": [{"name": p.get("name", ""), "id": p.get("id", ""), "child_count": len(p.get("children", []))} for p in data.get("document", {}).get("children", [])],
                "components_count": len(data.get("components", {})),
                "styles_count": len(data.get("styles", {})),
            })
        return json.dumps({"error": f"Figma API returned {resp.status_code}", "detail": resp.text[:500]})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _figma_get_components(file_key: str, page_name: str = "") -> str:
    """List all components in a Figma file with their properties."""
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True})
    try:
        resp = await _http.get(f"https://api.figma.com/v1/files/{file_key}/components", headers={"X-FIGMA-TOKEN": settings.figma_api_key})
        if resp.status_code == 200:
            data = resp.json()
            components = []
            for meta in data.get("meta", {}).get("components", []):
                comp = {
                    "key": meta.get("key", ""),
                    "name": meta.get("name", ""),
                    "description": meta.get("description", ""),
                    "containing_frame": meta.get("containing_frame", {}).get("name", ""),
                    "page_name": meta.get("containing_frame", {}).get("pageName", ""),
                }
                if not page_name or comp["page_name"].lower() == page_name.lower():
                    components.append(comp)
            return json.dumps({"file_key": file_key, "components": components, "total": len(components)})
        return json.dumps({"error": f"Figma API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _figma_get_styles(file_key: str) -> str:
    """Get all styles (colors, text, effects, grids) from a Figma file."""
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True})
    try:
        resp = await _http.get(f"https://api.figma.com/v1/files/{file_key}/styles", headers={"X-FIGMA-TOKEN": settings.figma_api_key})
        if resp.status_code == 200:
            data = resp.json()
            styles = []
            for s in data.get("meta", {}).get("styles", []):
                styles.append({
                    "key": s.get("key", ""),
                    "name": s.get("name", ""),
                    "style_type": s.get("style_type", ""),
                    "description": s.get("description", ""),
                })
            return json.dumps({"file_key": file_key, "styles": styles, "total": len(styles)})
        return json.dumps({"error": f"Figma API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _figma_export_assets(file_key: str, node_ids: str, format: str = "png", scale: str = "2") -> str:
    """Export assets (images, icons, illustrations) from Figma nodes."""
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True})
    try:
        ids = node_ids.replace(" ", "")
        resp = await _http.get(
            f"https://api.figma.com/v1/images/{file_key}?ids={ids}&format={format}&scale={scale}",
            headers={"X-FIGMA-TOKEN": settings.figma_api_key}
        )
        if resp.status_code == 200:
            data = resp.json()
            images = data.get("images", {})
            return json.dumps({"file_key": file_key, "format": format, "scale": scale, "exported_urls": images, "count": len(images)})
        return json.dumps({"error": f"Figma API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _figma_extract_design_tokens(file_key: str) -> str:
    """Extract design tokens (colors, typography, spacing) from Figma for CSS/Tailwind/code."""
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True, "note": "Will generate token structure from file styles when configured."})
    try:
        resp = await _http.get(f"https://api.figma.com/v1/files/{file_key}", headers={"X-FIGMA-TOKEN": settings.figma_api_key})
        if resp.status_code == 200:
            data = resp.json()
            styles = data.get("styles", {})
            tokens = {"colors": {}, "typography": {}, "effects": {}, "grids": {}}
            for style_id, style_info in styles.items():
                stype = style_info.get("styleType", "")
                name = style_info.get("name", style_id).replace("/", "-").replace(" ", "_").lower()
                if stype == "FILL":
                    tokens["colors"][name] = {"figma_style_id": style_id, "description": style_info.get("description", "")}
                elif stype == "TEXT":
                    tokens["typography"][name] = {"figma_style_id": style_id, "description": style_info.get("description", "")}
                elif stype == "EFFECT":
                    tokens["effects"][name] = {"figma_style_id": style_id}
                elif stype == "GRID":
                    tokens["grids"][name] = {"figma_style_id": style_id}
            return json.dumps({
                "file_key": file_key,
                "tokens": tokens,
                "export_formats": ["CSS custom properties", "Tailwind config", "SCSS variables", "JSON tokens"],
                "total_tokens": sum(len(v) for v in tokens.values()),
            })
        return json.dumps({"error": f"Figma API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _figma_get_team_projects(team_id: str = "") -> str:
    """List all projects in a Figma team."""
    tid = team_id or settings.figma_team_id
    if not settings.figma_api_key:
        return json.dumps({"error": "FIGMA_API_KEY required", "draft": True})
    if not tid:
        return json.dumps({"error": "FIGMA_TEAM_ID required"})
    try:
        resp = await _http.get(f"https://api.figma.com/v1/teams/{tid}/projects", headers={"X-FIGMA-TOKEN": settings.figma_api_key})
        if resp.status_code == 200:
            data = resp.json()
            projects = [{"id": p.get("id", ""), "name": p.get("name", "")} for p in data.get("projects", [])]
            return json.dumps({"team_id": tid, "projects": projects, "total": len(projects)})
        return json.dumps({"error": f"Figma API returned {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_figma_tools(registry):
    """Register all figma tools with the given registry."""
    from models import ToolParameter

    registry.register("figma_get_file", "Get Figma file data — pages, frames, components, styles.",
        [ToolParameter(name="file_key", description="Figma file key (from URL: figma.com/file/{key}/...)"),
         ToolParameter(name="components_only", description="Only fetch top-level structure", required=False)],
        _figma_get_file, "figma")

    registry.register("figma_get_components", "List all components in a Figma file with their properties and containing frames.",
        [ToolParameter(name="file_key", description="Figma file key"),
         ToolParameter(name="page_name", description="Filter by page name", required=False)],
        _figma_get_components, "figma")

    registry.register("figma_get_styles", "Get all styles (colors, text, effects, grids) from a Figma file.",
        [ToolParameter(name="file_key", description="Figma file key")],
        _figma_get_styles, "figma")

    registry.register("figma_export_assets", "Export assets (images, icons, illustrations) from Figma nodes as PNG/SVG/PDF.",
        [ToolParameter(name="file_key", description="Figma file key"),
         ToolParameter(name="node_ids", description="Comma-separated node IDs to export"),
         ToolParameter(name="format", description="Export format: png, svg, pdf, jpg", required=False),
         ToolParameter(name="scale", description="Scale factor: 1, 2, 3, 4", required=False)],
        _figma_export_assets, "figma")

    registry.register("figma_extract_design_tokens", "Extract design tokens (colors, typography, spacing) from Figma for CSS/Tailwind/code.",
        [ToolParameter(name="file_key", description="Figma file key")],
        _figma_extract_design_tokens, "figma")

    registry.register("figma_get_team_projects", "List all projects in a Figma team.",
        [ToolParameter(name="team_id", description="Figma team ID (defaults to FIGMA_TEAM_ID env var)", required=False)],
        _figma_get_team_projects, "figma")

    # ── Harvey AI Legal Tools ──

