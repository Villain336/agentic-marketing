"""
HubSpot CRM contacts, deals, activity logging, pipeline, and Cal.com booking.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _create_crm_contact(name: str, email: str, company: str = "",
                                title: str = "", source: str = "", notes: str = "") -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured. Set HUBSPOT_API_KEY.",
                           "draft": {"name": name, "email": email, "company": company}})
    name_parts = name.split(" ", 1)
    properties = {
        "email": email, "firstname": name_parts[0],
        "lastname": name_parts[1] if len(name_parts) > 1 else "",
        "company": company, "jobtitle": title,
    }
    try:
        resp = await _http.post("https://api.hubapi.com/crm/v3/objects/contacts",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": properties})
        if resp.status_code in (200, 201):
            return json.dumps({"contact_id": resp.json().get("id", ""), "created": True, "email": email})
        return json.dumps({"error": f"HubSpot {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _update_deal_stage(deal_id: str, stage: str) -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.patch(f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": {"dealstage": stage}})
        if resp.status_code == 200:
            return json.dumps({"updated": True, "deal_id": deal_id, "stage": stage})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _log_crm_activity(contact_id: str, activity_type: str,
                              notes: str, date: str = "") -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.post("https://api.hubapi.com/crm/v3/objects/notes",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"properties": {"hs_note_body": f"[{activity_type}] {notes}", "hs_timestamp": date or ""},
                  "associations": [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]})
        if resp.status_code in (200, 201):
            return json.dumps({"activity_id": resp.json().get("id", ""), "logged": True})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _get_pipeline_summary() -> str:
    api_key = getattr(settings, 'hubspot_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "HubSpot not configured."})
    try:
        resp = await _http.get("https://api.hubapi.com/crm/v3/objects/deals",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": 100, "properties": "dealstage,amount,dealname"})
        if resp.status_code == 200:
            deals = resp.json().get("results", [])
            stages: dict[str, dict] = {}
            total_value = 0.0
            for d in deals:
                props = d.get("properties", {})
                stage = props.get("dealstage", "unknown")
                amount = float(props.get("amount", 0) or 0)
                if stage not in stages:
                    stages[stage] = {"name": stage, "count": 0, "value": 0}
                stages[stage]["count"] += 1
                stages[stage]["value"] += amount
                total_value += amount
            return json.dumps({"stages": list(stages.values()), "total_pipeline_value": total_value, "total_deals": len(deals)})
        return json.dumps({"error": f"HubSpot {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _create_booking_link(event_type: str, duration: int = 30,
                                 availability: str = "") -> str:
    api_key = getattr(settings, 'calcom_api_key', '') or ""
    if not api_key:
        return json.dumps({"error": "Cal.com not configured. Set CALCOM_API_KEY.",
                           "draft": {"type": event_type, "duration": duration}})
    try:
        resp = await _http.post("https://api.cal.com/v1/event-types",
            params={"apiKey": api_key},
            json={"title": event_type, "slug": event_type.lower().replace(" ", "-"),
                  "length": duration, "description": f"Book a {duration}-min {event_type}"})
        if resp.status_code in (200, 201):
            slug = resp.json().get("event_type", {}).get("slug", event_type.lower().replace(" ", "-"))
            return json.dumps({"booking_url": f"https://cal.com/{slug}", "created": True})
        return json.dumps({"error": f"Cal.com {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



def register_crm_tools(registry):
    """Register all crm tools with the given registry."""
    from models import ToolParameter

    registry.register("create_crm_contact", "Create a contact in HubSpot CRM.",
        [ToolParameter(name="name", description="Full name"),
         ToolParameter(name="email", description="Email address"),
         ToolParameter(name="company", description="Company name", required=False),
         ToolParameter(name="title", description="Job title", required=False),
         ToolParameter(name="source", description="Lead source", required=False),
         ToolParameter(name="notes", description="Notes", required=False)],
        _create_crm_contact, "crm")

    registry.register("update_deal_stage", "Update a deal's pipeline stage in HubSpot.",
        [ToolParameter(name="deal_id", description="HubSpot deal ID"),
         ToolParameter(name="stage", description="New deal stage")],
        _update_deal_stage, "crm")

    registry.register("log_activity", "Log an activity against a CRM contact.",
        [ToolParameter(name="contact_id", description="HubSpot contact ID"),
         ToolParameter(name="activity_type", description="Type: email, call, meeting"),
         ToolParameter(name="notes", description="Activity notes"),
         ToolParameter(name="date", description="Activity date (ISO format)", required=False)],
        _log_crm_activity, "crm")

    registry.register("get_pipeline_summary", "Get summary of all deals in the HubSpot pipeline.",
        [], _get_pipeline_summary, "crm")

    # ── Calendar Tools ──

    registry.register("create_booking_link", "Create a booking link via Cal.com.",
        [ToolParameter(name="event_type", description="Event type name"),
         ToolParameter(name="duration", type="integer", description="Duration in minutes", required=False),
         ToolParameter(name="availability", description="Availability rules", required=False)],
        _create_booking_link, "calendar")

    # ── Marketing Expert Tools ──

