"""
PDF report generation and survey/feedback creation.
"""

from __future__ import annotations

import json
import base64

from config import settings
from tools.registry import _http, _http_long


async def _generate_pdf_report(title: str, sections: str, output_format: str = "url") -> str:
    """Generate a PDF report from HTML content via html-pdf-api or Browserless."""
    browserless_key = getattr(settings, 'browserless_api_key', '') or ""
    if browserless_key:
        try:
            html = f"""<html><head><style>body{{font-family:system-ui;padding:40px;max-width:800px;margin:0 auto}}
            h1{{color:#1a1a2e;border-bottom:2px solid #764ba2;padding-bottom:10px}}
            h2{{color:#764ba2;margin-top:30px}}p{{line-height:1.8;color:#333}}</style></head>
            <body><h1>{title}</h1>{sections}</body></html>"""
            resp = await _http_long.post("https://chrome.browserless.io/pdf",
                headers={"Content-Type": "application/json"},
                params={"token": browserless_key},
                json={"html": html, "options": {"format": "A4", "printBackground": True}})
            if resp.status_code == 200:
                pdf_b64 = base64.b64encode(resp.content).decode()
                return json.dumps({"generated": True, "title": title, "format": "pdf",
                                   "size_kb": len(resp.content) // 1024,
                                   "data_b64": pdf_b64[:500] + "..." if len(pdf_b64) > 500 else pdf_b64,
                                   "note": "PDF generated. Store via file storage tool."})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "PDF generation not configured. Set BROWSERLESS_API_KEY.",
                       "draft": {"title": title, "section_count": sections.count("<h2")}})



async def _create_survey(title: str, questions: str, redirect_url: str = "") -> str:
    """Create a survey/feedback form via Typeform API."""
    tf_key = getattr(settings, 'typeform_api_key', '') or ""
    if not tf_key:
        return json.dumps({"error": "Typeform not configured. Set TYPEFORM_API_KEY.",
                           "draft": {"title": title}})
    try:
        q_list = json.loads(questions) if isinstance(questions, str) else questions
    except json.JSONDecodeError:
        q_list = [{"title": questions, "type": "short_text"}]
    try:
        fields = []
        for q in q_list:
            field: dict[str, Any] = {
                "title": q.get("title", q) if isinstance(q, dict) else str(q),
                "type": q.get("type", "short_text") if isinstance(q, dict) else "short_text",
            }
            if isinstance(q, dict) and q.get("choices"):
                field["properties"] = {"choices": [{"label": c} for c in q["choices"]]}
            fields.append(field)
        resp = await _http.post("https://api.typeform.com/forms",
            headers={"Authorization": f"Bearer {tf_key}", "Content-Type": "application/json"},
            json={"title": title, "fields": fields,
                  "thankyou_screens": [{"title": "Thank you!", "properties": {"redirect_url": redirect_url} if redirect_url else {}}]})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"form_id": data.get("id", ""),
                               "url": f"https://form.typeform.com/to/{data.get('id', '')}",
                               "created": True, "fields_count": len(fields)})
        return json.dumps({"error": f"Typeform {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_reporting_tools(registry):
    """Register all reporting tools with the given registry."""
    from models import ToolParameter

    registry.register("generate_pdf_report", "Generate a PDF report from HTML sections.",
        [ToolParameter(name="title", description="Report title"),
         ToolParameter(name="sections", description="HTML content sections"),
         ToolParameter(name="output_format", description="Output: url or base64", required=False)],
        _generate_pdf_report, "reporting")

    registry.register("create_survey", "Create a survey/feedback form via Typeform.",
        [ToolParameter(name="title", description="Survey title"),
         ToolParameter(name="questions", description="JSON array of question objects"),
         ToolParameter(name="redirect_url", description="URL to redirect after completion", required=False)],
        _create_survey, "reporting")

    # ── Site Deployment Tools ──

