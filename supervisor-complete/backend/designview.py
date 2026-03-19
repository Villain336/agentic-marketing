"""
Omni OS Backend — Design View / Interactive Visual Editor
Real-time visual editing canvas for agent-generated assets.
Competes with Manus 1.6's Design View and OpenClaw's Live Canvas.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.designview")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class DesignCanvas(BaseModel):
    """A visual editing canvas for a campaign's design assets."""
    id: str = Field(default_factory=lambda: f"canvas_{uuid.uuid4().hex[:12]}")
    campaign_id: str
    name: str = "Untitled Canvas"
    width: int = 1440
    height: int = 900
    background: str = "#ffffff"
    layers: list["DesignLayer"] = []
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DesignLayer(BaseModel):
    """A single layer in the design canvas."""
    id: str = Field(default_factory=lambda: f"layer_{uuid.uuid4().hex[:8]}")
    type: str = "element"          # element | group | component | template
    name: str = ""
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    z_index: int = 0
    elements: list["DesignElement"] = []


class DesignElement(BaseModel):
    """An element on the canvas (text, shape, image, component)."""
    id: str = Field(default_factory=lambda: f"el_{uuid.uuid4().hex[:8]}")
    type: str                      # text | image | shape | button | card | hero | nav | footer | form
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 50
    rotation: float = 0
    properties: dict = {}          # Type-specific properties
    styles: dict = {}              # CSS-like styles
    interactions: list[dict] = []  # Click handlers, hover states, etc.
    children: list["DesignElement"] = []
    source_agent: str = ""         # Which agent generated this


class DesignTemplate(BaseModel):
    """Pre-built design templates for common marketing assets."""
    id: str = Field(default_factory=lambda: f"tmpl_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    category: str = "landing_page"  # landing_page | email | social | ad | presentation
    preview_url: str = ""
    canvas_data: dict = {}         # Serialized canvas
    tags: list[str] = []
    installs: int = 0


class DesignExport(BaseModel):
    """Export configuration for a design."""
    format: str = "html"           # html | png | svg | pdf | figma | react
    quality: int = 100
    scale: float = 1.0
    include_interactions: bool = True
    responsive: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

BUILT_IN_TEMPLATES = [
    DesignTemplate(
        name="SaaS Landing Page",
        description="Hero section + features grid + pricing + CTA + testimonials + footer",
        category="landing_page", tags=["saas", "startup", "conversion"],
        canvas_data={
            "sections": ["hero", "features", "pricing", "testimonials", "cta", "footer"],
            "style": "modern_minimal",
        },
    ),
    DesignTemplate(
        name="Email Newsletter",
        description="Header logo + hero image + article blocks + CTA button + footer",
        category="email", tags=["newsletter", "email", "engagement"],
        canvas_data={
            "sections": ["header", "hero_image", "article_1", "article_2", "cta", "footer"],
            "style": "clean_corporate",
            "max_width": 600,
        },
    ),
    DesignTemplate(
        name="Social Media Card",
        description="Square format with headline, subtext, and brand elements",
        category="social", tags=["social", "instagram", "linkedin"],
        canvas_data={
            "width": 1080, "height": 1080,
            "sections": ["background", "headline", "subtext", "logo", "cta"],
            "style": "bold_gradient",
        },
    ),
    DesignTemplate(
        name="Facebook/Google Ad",
        description="Ad creative with headline, description, image, and CTA",
        category="ad", tags=["ad", "facebook", "google", "conversion"],
        canvas_data={
            "variants": ["1200x628", "1080x1080", "1080x1920"],
            "sections": ["image", "headline", "description", "cta", "logo"],
            "style": "attention_grabbing",
        },
    ),
    DesignTemplate(
        name="Pitch Deck Slide",
        description="Clean presentation slide with title, content, and visuals",
        category="presentation", tags=["pitch", "deck", "investor"],
        canvas_data={
            "width": 1920, "height": 1080,
            "sections": ["title", "content", "visual", "footer"],
            "style": "professional_clean",
        },
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

COMPONENT_LIBRARY = {
    "hero_section": {
        "type": "hero",
        "default_properties": {
            "headline": "Build Something Amazing",
            "subheadline": "The platform that helps you launch faster",
            "cta_text": "Get Started",
            "cta_url": "#",
            "background_type": "gradient",
            "background_value": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        },
        "default_styles": {
            "padding": "80px 40px",
            "text_align": "center",
            "font_size_headline": "48px",
            "font_size_sub": "20px",
            "color": "#ffffff",
        },
    },
    "feature_card": {
        "type": "card",
        "default_properties": {
            "icon": "bolt",
            "title": "Feature Name",
            "description": "Brief description of this feature and its benefits.",
        },
        "default_styles": {
            "padding": "24px",
            "border_radius": "12px",
            "background": "#ffffff",
            "box_shadow": "0 2px 8px rgba(0,0,0,0.08)",
        },
    },
    "pricing_card": {
        "type": "card",
        "default_properties": {
            "plan_name": "Pro",
            "price": "$49",
            "period": "/month",
            "features": ["Feature 1", "Feature 2", "Feature 3"],
            "cta_text": "Start Free Trial",
            "highlighted": False,
        },
        "default_styles": {
            "padding": "32px",
            "border_radius": "16px",
            "border": "1px solid #e2e8f0",
        },
    },
    "testimonial": {
        "type": "card",
        "default_properties": {
            "quote": "This product changed how we work.",
            "author": "Jane Doe",
            "role": "CEO at Company",
            "avatar_url": "",
            "rating": 5,
        },
        "default_styles": {
            "padding": "24px",
            "font_style": "italic",
            "border_left": "4px solid #667eea",
        },
    },
    "cta_button": {
        "type": "button",
        "default_properties": {
            "text": "Get Started",
            "url": "#",
            "variant": "primary",
        },
        "default_styles": {
            "padding": "12px 32px",
            "border_radius": "8px",
            "font_weight": "600",
            "background": "#667eea",
            "color": "#ffffff",
        },
    },
    "nav_bar": {
        "type": "nav",
        "default_properties": {
            "logo_text": "Brand",
            "links": ["Features", "Pricing", "About", "Contact"],
            "cta_text": "Sign Up",
        },
        "default_styles": {
            "padding": "16px 40px",
            "background": "#ffffff",
            "border_bottom": "1px solid #e2e8f0",
        },
    },
    "footer": {
        "type": "footer",
        "default_properties": {
            "company_name": "Company Inc.",
            "columns": [
                {"title": "Product", "links": ["Features", "Pricing", "Docs"]},
                {"title": "Company", "links": ["About", "Blog", "Careers"]},
                {"title": "Legal", "links": ["Privacy", "Terms"]},
            ],
            "social_links": ["twitter", "linkedin", "github"],
        },
        "default_styles": {
            "padding": "60px 40px",
            "background": "#1a202c",
            "color": "#a0aec0",
        },
    },
    "form": {
        "type": "form",
        "default_properties": {
            "fields": [
                {"name": "email", "type": "email", "placeholder": "Enter your email", "required": True},
            ],
            "submit_text": "Subscribe",
            "action_url": "",
        },
        "default_styles": {
            "max_width": "400px",
            "padding": "24px",
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN VIEW ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DesignViewEngine:
    """
    Interactive visual editor for agent-generated marketing assets.
    Supports real-time editing, component library, templates, and multi-format export.
    """

    def __init__(self):
        self._canvases: dict[str, DesignCanvas] = {}
        self._templates = {t.id: t for t in BUILT_IN_TEMPLATES}
        self._edit_history: dict[str, list[dict]] = {}  # canvas_id -> undo stack

    # ── Canvas Management ────────────────────────────────────────────────────

    def create_canvas(self, campaign_id: str, name: str = "Untitled",
                      template_id: str = "", width: int = 1440,
                      height: int = 900) -> DesignCanvas:
        """Create a new design canvas, optionally from a template."""
        canvas = DesignCanvas(
            campaign_id=campaign_id, name=name,
            width=width, height=height,
        )

        if template_id and template_id in self._templates:
            template = self._templates[template_id]
            canvas = self._apply_template(canvas, template)

        self._canvases[canvas.id] = canvas
        self._edit_history[canvas.id] = []
        logger.info(f"Canvas created: {canvas.id} for campaign {campaign_id}")
        return canvas

    def _apply_template(self, canvas: DesignCanvas,
                         template: DesignTemplate) -> DesignCanvas:
        """Apply a template's structure to a canvas."""
        canvas.name = template.name
        sections = template.canvas_data.get("sections", [])

        for i, section_name in enumerate(sections):
            component = COMPONENT_LIBRARY.get(
                f"{section_name}_section",
                COMPONENT_LIBRARY.get(section_name, COMPONENT_LIBRARY.get("hero_section")),
            )

            if component:
                element = DesignElement(
                    type=component["type"],
                    x=0, y=i * 400, width=canvas.width, height=400,
                    properties=component.get("default_properties", {}).copy(),
                    styles=component.get("default_styles", {}).copy(),
                )
                layer = DesignLayer(
                    name=section_name, z_index=i,
                    elements=[element],
                )
                canvas.layers.append(layer)

        return canvas

    def get_canvas(self, canvas_id: str) -> Optional[DesignCanvas]:
        return self._canvases.get(canvas_id)

    def list_canvases(self, campaign_id: str) -> list[DesignCanvas]:
        return [
            c for c in self._canvases.values()
            if c.campaign_id == campaign_id
        ]

    # ── Element Operations ───────────────────────────────────────────────────

    def add_element(self, canvas_id: str, layer_id: str,
                    element: DesignElement) -> Optional[DesignCanvas]:
        """Add an element to a layer."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return None

        for layer in canvas.layers:
            if layer.id == layer_id:
                layer.elements.append(element)
                self._record_edit(canvas_id, "add_element", {"element_id": element.id})
                canvas.updated_at = datetime.utcnow()
                canvas.version += 1
                return canvas

        return None

    def update_element(self, canvas_id: str, element_id: str,
                       updates: dict) -> Optional[DesignElement]:
        """Update an element's properties, styles, or position."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return None

        element = self._find_element(canvas, element_id)
        if not element:
            return None

        # Record for undo
        old_state = element.model_dump()
        self._record_edit(canvas_id, "update_element", {
            "element_id": element_id, "old_state": old_state,
        })

        # Apply updates
        for k, v in updates.items():
            if k == "properties":
                element.properties.update(v)
            elif k == "styles":
                element.styles.update(v)
            elif hasattr(element, k):
                setattr(element, k, v)

        canvas.updated_at = datetime.utcnow()
        canvas.version += 1
        return element

    def delete_element(self, canvas_id: str, element_id: str) -> bool:
        """Delete an element from the canvas."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return False

        for layer in canvas.layers:
            layer.elements = [e for e in layer.elements if e.id != element_id]

        canvas.updated_at = datetime.utcnow()
        canvas.version += 1
        return True

    def add_component(self, canvas_id: str, component_name: str,
                      x: float = 0, y: float = 0,
                      overrides: dict = None) -> Optional[DesignElement]:
        """Add a component from the library to the canvas."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return None

        component = COMPONENT_LIBRARY.get(component_name)
        if not component:
            return None

        props = component.get("default_properties", {}).copy()
        styles = component.get("default_styles", {}).copy()
        if overrides:
            props.update(overrides.get("properties", {}))
            styles.update(overrides.get("styles", {}))

        element = DesignElement(
            type=component["type"],
            x=x, y=y, width=400, height=200,
            properties=props, styles=styles,
        )

        # Add to first unlocked layer, or create one
        target_layer = None
        for layer in canvas.layers:
            if not layer.locked:
                target_layer = layer
                break

        if not target_layer:
            target_layer = DesignLayer(name="New Layer", z_index=len(canvas.layers))
            canvas.layers.append(target_layer)

        target_layer.elements.append(element)
        canvas.updated_at = datetime.utcnow()
        canvas.version += 1
        return element

    def _find_element(self, canvas: DesignCanvas,
                       element_id: str) -> Optional[DesignElement]:
        """Find an element by ID across all layers."""
        for layer in canvas.layers:
            for element in layer.elements:
                if element.id == element_id:
                    return element
                for child in element.children:
                    if child.id == element_id:
                        return child
        return None

    # ── Undo/Redo ────────────────────────────────────────────────────────────

    def _record_edit(self, canvas_id: str, action: str, data: dict):
        if canvas_id not in self._edit_history:
            self._edit_history[canvas_id] = []
        self._edit_history[canvas_id].append({
            "action": action, "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Keep last 50 edits
        self._edit_history[canvas_id] = self._edit_history[canvas_id][-50:]

    def get_edit_history(self, canvas_id: str) -> list[dict]:
        return self._edit_history.get(canvas_id, [])

    # ── Export ───────────────────────────────────────────────────────────────

    def export_html(self, canvas_id: str, responsive: bool = True) -> str:
        """Export canvas as production-ready HTML."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return ""

        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"<title>{canvas.name}</title>",
            "<style>",
            "* { margin: 0; padding: 0; box-sizing: border-box; }",
            f"body {{ background: {canvas.background}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}",
        ]

        if responsive:
            html_parts.append("@media (max-width: 768px) { .section { padding: 40px 20px !important; } }")

        html_parts.extend(["</style>", "</head>", "<body>"])

        for layer in sorted(canvas.layers, key=lambda l: l.z_index):
            if not layer.visible:
                continue
            for element in layer.elements:
                html_parts.append(self._element_to_html(element))

        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts)

    def _element_to_html(self, element: DesignElement) -> str:
        """Convert a design element to HTML."""
        styles = "; ".join(f"{k.replace('_', '-')}: {v}" for k, v in element.styles.items())
        props = element.properties

        if element.type == "hero":
            return (
                f'<section class="section" style="{styles}">'
                f'<h1 style="font-size: {props.get("font_size_headline", "48px")}; margin-bottom: 16px;">'
                f'{props.get("headline", "")}</h1>'
                f'<p style="font-size: {props.get("font_size_sub", "20px")}; margin-bottom: 32px; opacity: 0.9;">'
                f'{props.get("subheadline", "")}</p>'
                f'<a href="{props.get("cta_url", "#")}" style="display: inline-block; padding: 16px 40px; '
                f'background: rgba(255,255,255,0.2); border-radius: 8px; color: white; text-decoration: none; '
                f'font-weight: 600;">{props.get("cta_text", "Get Started")}</a>'
                f'</section>'
            )
        elif element.type == "card":
            features_html = ""
            if "features" in props:
                features_html = "<ul>" + "".join(f"<li>{f}</li>" for f in props["features"]) + "</ul>"
            return (
                f'<div style="{styles}">'
                f'<h3>{props.get("title", props.get("plan_name", ""))}</h3>'
                f'<p>{props.get("description", "")}</p>'
                f'{features_html}'
                f'</div>'
            )
        elif element.type == "button":
            return (
                f'<a href="{props.get("url", "#")}" style="{styles}; display: inline-block; '
                f'text-decoration: none; cursor: pointer;">{props.get("text", "Click")}</a>'
            )
        elif element.type == "text":
            return f'<p style="{styles}">{props.get("content", "")}</p>'
        elif element.type == "image":
            return f'<img src="{props.get("src", "")}" alt="{props.get("alt", "")}" style="{styles}; max-width: 100%;">'
        elif element.type == "nav":
            links = " ".join(f'<a href="#" style="margin: 0 16px; text-decoration: none; color: inherit;">{l}</a>'
                             for l in props.get("links", []))
            return (
                f'<nav style="{styles}; display: flex; align-items: center; justify-content: space-between;">'
                f'<strong>{props.get("logo_text", "")}</strong>'
                f'<div>{links}</div>'
                f'<a href="#" style="padding: 8px 20px; background: #667eea; color: white; border-radius: 6px; '
                f'text-decoration: none;">{props.get("cta_text", "Sign Up")}</a>'
                f'</nav>'
            )
        elif element.type == "footer":
            return (
                f'<footer style="{styles}">'
                f'<p>&copy; {props.get("company_name", "Company")} {datetime.utcnow().year}</p>'
                f'</footer>'
            )
        elif element.type == "form":
            fields = ""
            for field in props.get("fields", []):
                fields += (
                    f'<input type="{field.get("type", "text")}" '
                    f'placeholder="{field.get("placeholder", "")}" '
                    f'style="width: 100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 12px;">'
                )
            return (
                f'<form style="{styles}">'
                f'{fields}'
                f'<button type="submit" style="width: 100%; padding: 12px; background: #667eea; '
                f'color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">'
                f'{props.get("submit_text", "Submit")}</button>'
                f'</form>'
            )

        return f'<div style="{styles}"><!-- {element.type} --></div>'

    def export_react(self, canvas_id: str) -> str:
        """Export canvas as a React component."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return ""

        component_name = canvas.name.replace(" ", "").replace("-", "")
        lines = [
            f'import React from "react";',
            f"",
            f"export default function {component_name}() {{",
            f"  return (",
            f"    <div>",
        ]

        for layer in sorted(canvas.layers, key=lambda l: l.z_index):
            if not layer.visible:
                continue
            for element in layer.elements:
                lines.append(f"      {self._element_to_jsx(element)}")

        lines.extend([
            f"    </div>",
            f"  );",
            f"}}",
        ])
        return "\n".join(lines)

    def _element_to_jsx(self, element: DesignElement) -> str:
        """Convert a design element to JSX."""
        styles = ", ".join(
            f'"{k}": "{v}"' for k, v in element.styles.items()
        )
        props = element.properties

        if element.type == "hero":
            return (
                f'<section style={{{{{styles}}}}}>'
                f'<h1>{props.get("headline", "")}</h1>'
                f'<p>{props.get("subheadline", "")}</p>'
                f'<a href="{props.get("cta_url", "#")}">{props.get("cta_text", "")}</a>'
                f'</section>'
            )
        elif element.type == "button":
            return f'<a href="{props.get("url", "#")}" style={{{{{styles}}}}}>{props.get("text", "")}</a>'
        else:
            return f'<div style={{{{{styles}}}}}>/* {element.type} */</div>'

    # ── Templates ────────────────────────────────────────────────────────────

    def get_templates(self, category: str = "") -> list[DesignTemplate]:
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates

    def get_component_library(self) -> dict:
        return {
            name: {
                "type": comp["type"],
                "properties": list(comp.get("default_properties", {}).keys()),
                "styles": list(comp.get("default_styles", {}).keys()),
            }
            for name, comp in COMPONENT_LIBRARY.items()
        }

    # ── Agent Integration ────────────────────────────────────────────────────

    def create_from_agent_output(self, campaign_id: str, agent_id: str,
                                  output: dict) -> DesignCanvas:
        """
        Create a canvas from agent output.
        E.g., sitelaunch agent generates HTML → parse into canvas elements.
        """
        canvas = self.create_canvas(campaign_id, name=f"Generated by {agent_id}")

        # If output contains landing page HTML, parse it into components
        if "landing_page_html" in output:
            layer = DesignLayer(name="Generated Layout", z_index=0)
            hero = DesignElement(
                type="hero", x=0, y=0, width=canvas.width, height=600,
                properties={
                    "headline": output.get("headline", "Your Product"),
                    "subheadline": output.get("subheadline", ""),
                    "cta_text": output.get("cta_text", "Get Started"),
                    "background_type": "gradient",
                    "background_value": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                },
                styles={"padding": "80px 40px", "text_align": "center", "color": "#ffffff"},
                source_agent=agent_id,
            )
            layer.elements.append(hero)
            canvas.layers.append(layer)

        # If output contains brand system, apply it
        if "brand_system" in output:
            brand = output["brand_system"]
            canvas.background = brand.get("background_color", "#ffffff")

        canvas.updated_at = datetime.utcnow()
        return canvas


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

design_view = DesignViewEngine()
