"""
Logo generation, color palette, font pairing, and asset upload.
"""

from __future__ import annotations

import json
import base64

from config import settings
from tools.registry import _http


from tools.content import _generate_image
async def _generate_logo(brand_name: str, style: str = "modern minimal",
                           icon_description: str = "") -> str:
    """Generate logo concepts using image generation API."""
    prompt = f"Professional logo design for '{brand_name}'. Style: {style}."
    if icon_description:
        prompt += f" Icon: {icon_description}."
    prompt += " Clean vector-style, white background, suitable for business use."
    return await _generate_image(prompt, style="logo design", size="1024x1024")



async def _generate_color_palette(industry: str, personality: str,
                                    base_color: str = "") -> str:
    """Generate a harmonious color palette based on brand attributes."""
    palettes = {
        "professional": {"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936",
                         "success": "#38a169", "warning": "#d69e2e", "error": "#e53e3e",
                         "bg_primary": "#ffffff", "bg_secondary": "#f7fafc",
                         "text_primary": "#1a202c", "text_secondary": "#4a5568"},
        "creative": {"primary": "#6b46c1", "secondary": "#d53f8c", "accent": "#38b2ac",
                     "success": "#48bb78", "warning": "#ecc94b", "error": "#fc8181",
                     "bg_primary": "#ffffff", "bg_secondary": "#faf5ff",
                     "text_primary": "#1a202c", "text_secondary": "#553c9a"},
        "bold": {"primary": "#e53e3e", "secondary": "#1a202c", "accent": "#ecc94b",
                 "success": "#48bb78", "warning": "#ed8936", "error": "#fc8181",
                 "bg_primary": "#ffffff", "bg_secondary": "#fff5f5",
                 "text_primary": "#1a202c", "text_secondary": "#742a2a"},
        "minimal": {"primary": "#1a202c", "secondary": "#718096", "accent": "#3182ce",
                    "success": "#38a169", "warning": "#d69e2e", "error": "#e53e3e",
                    "bg_primary": "#ffffff", "bg_secondary": "#f7fafc",
                    "text_primary": "#1a202c", "text_secondary": "#a0aec0"},
        "warm": {"primary": "#c05621", "secondary": "#744210", "accent": "#2b6cb0",
                 "success": "#276749", "warning": "#975a16", "error": "#9b2c2c",
                 "bg_primary": "#fffaf0", "bg_secondary": "#fefcbf",
                 "text_primary": "#1a202c", "text_secondary": "#744210"},
    }
    personality_lower = personality.lower()
    selected = palettes.get(personality_lower, palettes["professional"])
    if base_color and base_color.startswith("#"):
        selected["primary"] = base_color
    return json.dumps({
        "industry": industry, "personality": personality,
        "palette": selected,
        "css_variables": "\n".join(f"  --color-{k}: {v};" for k, v in selected.items()),
        "usage_rules": {
            "primary": "Main CTAs, headers, key interactive elements",
            "secondary": "Supporting elements, secondary buttons, borders",
            "accent": "Highlights, badges, attention-grabbing elements",
            "bg_primary": "Main page background",
            "bg_secondary": "Cards, sections, alternate rows",
        },
    })



async def _get_font_pairing(style: str = "modern", industry: str = "") -> str:
    """Get Google Fonts pairing recommendation."""
    pairings = {
        "modern": {"display": "Inter", "body": "Inter", "mono": "JetBrains Mono",
                   "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');"},
        "elegant": {"display": "Playfair Display", "body": "Source Sans Pro", "mono": "Source Code Pro",
                    "weights": "400;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+Pro:wght@400;600&display=swap');"},
        "startup": {"display": "Space Grotesk", "body": "DM Sans", "mono": "Fira Code",
                    "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500&display=swap');"},
        "corporate": {"display": "IBM Plex Sans", "body": "IBM Plex Sans", "mono": "IBM Plex Mono",
                      "weights": "400;500;600;700", "import": "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');"},
        "bold": {"display": "Outfit", "body": "Work Sans", "mono": "JetBrains Mono",
                 "weights": "400;500;600;700;800", "import": "@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Work+Sans:wght@400;500&display=swap');"},
    }
    selected = pairings.get(style.lower(), pairings["modern"])
    return json.dumps({
        "style": style, "fonts": selected,
        "size_scale": {
            "xs": "12px", "sm": "14px", "base": "16px", "lg": "18px",
            "xl": "20px", "2xl": "24px", "3xl": "30px", "4xl": "36px", "5xl": "48px",
        },
        "line_heights": {"tight": "1.25", "normal": "1.5", "relaxed": "1.75"},
    })



async def _upload_asset(file_data: str, filename: str, content_type: str = "image/png") -> str:
    """Upload a brand asset to Cloudflare R2 or Supabase Storage."""
    r2_key = getattr(settings, 'cloudflare_r2_access_key', '') or ""
    r2_secret = getattr(settings, 'cloudflare_r2_secret_key', '') or ""
    r2_bucket = getattr(settings, 'cloudflare_r2_bucket', '') or ""
    account_id = getattr(settings, 'cloudflare_account_id', '') or ""
    if r2_key and r2_secret and r2_bucket and account_id:
        try:
            resp = await _http.put(
                f"https://{account_id}.r2.cloudflarestorage.com/{r2_bucket}/{filename}",
                headers={"Content-Type": content_type},
                content=base64.b64decode(file_data) if file_data.startswith("data:") is False else file_data.encode())
            if resp.status_code in (200, 201):
                return json.dumps({"uploaded": True, "filename": filename,
                                   "url": f"https://{r2_bucket}.{account_id}.r2.dev/{filename}",
                                   "provider": "cloudflare_r2"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_service_key or settings.supabase_anon_key
    if supabase_url and supabase_key:
        try:
            resp = await _http.post(
                f"{supabase_url}/storage/v1/object/brand-assets/{filename}",
                headers={"Authorization": f"Bearer {supabase_key}",
                         "Content-Type": content_type},
                content=base64.b64decode(file_data) if len(file_data) > 100 else file_data.encode())
            if resp.status_code in (200, 201):
                return json.dumps({"uploaded": True, "filename": filename,
                                   "url": f"{supabase_url}/storage/v1/object/public/brand-assets/{filename}",
                                   "provider": "supabase_storage"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "No file storage configured. Set CLOUDFLARE_R2_* or SUPABASE_* keys.",
                       "draft": {"filename": filename, "size": len(file_data)}})



def register_design_tools(registry):
    """Register all design tools with the given registry."""
    from models import ToolParameter

    registry.register("generate_logo", "Generate logo concepts using AI image generation.",
        [ToolParameter(name="brand_name", description="Brand/company name"),
         ToolParameter(name="style", description="Style: modern minimal, bold, elegant, playful", required=False),
         ToolParameter(name="icon_description", description="Optional icon/symbol description", required=False)],
        _generate_logo, "design")

    registry.register("generate_color_palette", "Generate a harmonious brand color palette.",
        [ToolParameter(name="industry", description="Industry/niche"),
         ToolParameter(name="personality", description="Brand personality: professional, creative, bold, minimal, warm"),
         ToolParameter(name="base_color", description="Optional base color hex (e.g. #1a365d)", required=False)],
        _generate_color_palette, "design")

    registry.register("get_font_pairing", "Get Google Fonts pairing recommendation with size scale.",
        [ToolParameter(name="style", description="Style: modern, elegant, startup, corporate, bold"),
         ToolParameter(name="industry", description="Industry for context", required=False)],
        _get_font_pairing, "design")

    registry.register("upload_asset", "Upload a brand asset to Cloudflare R2 or Supabase Storage.",
        [ToolParameter(name="file_data", description="Base64-encoded file data"),
         ToolParameter(name="filename", description="Filename with extension"),
         ToolParameter(name="content_type", description="MIME type (e.g. image/png)", required=False)],
        _upload_asset, "design")

    # ── Supervisor Tools ──

