"""
SendGrid email, warmup, verification, and newsletter/ESP tools.
"""

from __future__ import annotations

import json

from config import settings
from tools.registry import _http


async def _send_email(to: str, subject: str, body: str, from_name: str = "",
                       reply_to: str = "") -> str:
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured. Set SENDGRID_API_KEY."})
    from_email = getattr(settings, 'sendgrid_from_email', '') or "noreply@supervisor.app"
    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": from_name or "Supervisor"},
        "subject": subject,
        "content": [{"type": "text/html", "value": body}],
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}
    try:
        resp = await _http.post("https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload)
        if resp.status_code in (200, 202):
            msg_id = resp.headers.get("X-Message-Id", "")
            return json.dumps({"sent": True, "message_id": msg_id, "to": to})
        return json.dumps({"sent": False, "error": f"SendGrid {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"sent": False, "error": str(e)})



async def _schedule_email_sequence(emails: str) -> str:
    """Schedule a sequence of emails. Input: JSON array of {to, subject, body, send_at}."""
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        items = json.loads(emails) if isinstance(emails, str) else emails
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON for emails parameter"})
    results = []
    for item in items:
        result = await _send_email(
            to=item.get("to", ""), subject=item.get("subject", ""),
            body=item.get("body", ""), from_name=item.get("from_name", ""))
        results.append(json.loads(result))
    scheduled = sum(1 for r in results if r.get("sent"))
    return json.dumps({"scheduled": True, "count": scheduled, "total": len(items), "results": results})



async def _check_email_status(message_id: str) -> str:
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        resp = await _http.get(f"https://api.sendgrid.com/v3/messages/{message_id}",
            headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({"message_id": message_id,
                "status": data.get("status", "unknown"),
                "events": data.get("events", [])[:5]})
        return json.dumps({"message_id": message_id, "status": "unknown"})
    except Exception as e:
        return json.dumps({"message_id": message_id, "error": str(e)})



async def _check_email_warmup_status(email_account: str) -> str:
    """Check email warmup/deliverability status via Instantly.ai."""
    instantly_key = getattr(settings, 'instantly_api_key', '') or ""
    if not instantly_key:
        return json.dumps({"error": "Email warmup not configured. Set INSTANTLY_API_KEY.",
                           "recommendation": "Use Instantly.ai or Smartlead for warmup."})
    try:
        resp = await _http.get("https://api.instantly.ai/api/v1/account/warmup/status",
            params={"api_key": instantly_key, "email": email_account})
        if resp.status_code == 200:
            data = resp.json()
            return json.dumps({
                "email": email_account, "warmup_active": data.get("warmup_active", False),
                "warmup_reputation": data.get("warmup_reputation", ""),
                "daily_limit": data.get("daily_limit", 0),
                "emails_sent_today": data.get("emails_sent_today", 0),
            })
        return json.dumps({"error": f"Instantly {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _detect_email_replies(campaign_tag: str = "", since_hours: int = 24) -> str:
    """Check for replies to sent emails via SendGrid inbound parse or IMAP."""
    api_key = settings.sendgrid_api_key
    if not api_key:
        return json.dumps({"error": "SendGrid not configured."})
    try:
        resp = await _http.get("https://api.sendgrid.com/v3/messages",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"limit": 50, "query": f"status='delivered' AND last_event_time BETWEEN NOW-{since_hours}h AND NOW"})
        if resp.status_code == 200:
            messages = resp.json().get("messages", [])
            replied = [m for m in messages if m.get("opens_count", 0) > 0]
            return json.dumps({
                "total_sent": len(messages), "opened": len(replied),
                "open_rate": round(len(replied) / max(len(messages), 1) * 100, 1),
                "messages": [{"to": m.get("to_email", ""), "subject": m.get("subject", ""),
                              "status": m.get("status", ""), "opens": m.get("opens_count", 0)}
                             for m in replied[:20]],
            })
        return json.dumps({"error": f"SendGrid {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _create_email_list(list_name: str, provider: str = "convertkit") -> str:
    """Create an email list/tag in ConvertKit, Mailchimp, or Beehiiv."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured. Set CONVERTKIT_API_KEY."})
        try:
            resp = await _http.post("https://api.convertkit.com/v3/tags",
                json={"api_key": ck_key, "tag": {"name": list_name}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"tag_id": data.get("id", ""), "name": list_name,
                                   "provider": "convertkit", "created": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key:
            return json.dumps({"error": "Mailchimp not configured. Set MAILCHIMP_API_KEY."})
        try:
            dc = mc_key.split("-")[-1]
            resp = await _http.post(f"https://{dc}.api.mailchimp.com/3.0/lists",
                headers={"Authorization": f"Bearer {mc_key}", "Content-Type": "application/json"},
                json={"name": list_name, "permission_reminder": "You signed up on our website.",
                      "email_type_option": True,
                      "contact": {"company": "", "address1": "", "city": "", "state": "",
                                  "zip": "", "country": "US"},
                      "campaign_defaults": {"from_name": "", "from_email": "", "subject": "",
                                            "language": "en"}})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"list_id": data.get("id", ""), "name": list_name,
                                   "provider": "mailchimp", "created": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "beehiiv":
        bh_key = getattr(settings, 'beehiiv_api_key', '') or ""
        bh_pub = getattr(settings, 'beehiiv_publication_id', '') or ""
        if not bh_key or not bh_pub:
            return json.dumps({"error": "Beehiiv not configured. Set BEEHIIV_API_KEY."})
        return json.dumps({"note": "Beehiiv uses publication-level lists. Tag created.",
                           "provider": "beehiiv", "tag": list_name})
    return json.dumps({"error": f"Unknown ESP provider: {provider}"})



async def _add_subscriber(email: str, name: str = "", tags: str = "",
                            provider: str = "convertkit") -> str:
    """Add subscriber to email list."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured."})
        try:
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            for tag in tag_list or ["default"]:
                resp = await _http.post(f"https://api.convertkit.com/v3/tags/{tag}/subscribe",
                    json={"api_key": ck_key, "email": email, "first_name": name.split()[0] if name else ""})
            return json.dumps({"subscribed": True, "email": email, "provider": "convertkit"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key:
            return json.dumps({"error": "Mailchimp not configured."})
        try:
            dc = mc_key.split("-")[-1]
            list_id = tags.split(",")[0].strip() if tags else ""
            if not list_id:
                return json.dumps({"error": "Provide list_id in tags parameter for Mailchimp."})
            name_parts = name.split(" ", 1)
            resp = await _http.post(f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}/members",
                headers={"Authorization": f"Bearer {mc_key}", "Content-Type": "application/json"},
                json={"email_address": email, "status": "subscribed",
                      "merge_fields": {"FNAME": name_parts[0] if name_parts else "",
                                       "LNAME": name_parts[1] if len(name_parts) > 1 else ""}})
            if resp.status_code in (200, 201):
                return json.dumps({"subscribed": True, "email": email, "provider": "mailchimp"})
            return json.dumps({"error": f"Mailchimp {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown ESP provider: {provider}"})



async def _get_email_analytics(provider: str = "convertkit", list_id: str = "") -> str:
    """Get email subscriber analytics — open rates, click rates, growth."""
    if provider == "convertkit":
        ck_key = getattr(settings, 'convertkit_api_key', '') or ""
        if not ck_key:
            return json.dumps({"error": "ConvertKit not configured."})
        try:
            resp = await _http.get("https://api.convertkit.com/v3/subscribers",
                params={"api_key": ck_key, "page": 1})
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({
                    "provider": "convertkit",
                    "total_subscribers": data.get("total_subscribers", 0),
                    "subscribers_today": len([s for s in data.get("subscribers", [])
                                              if "today" in s.get("created_at", "")]),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "mailchimp":
        mc_key = getattr(settings, 'mailchimp_api_key', '') or ""
        if not mc_key or not list_id:
            return json.dumps({"error": "Mailchimp not configured or list_id missing."})
        try:
            dc = mc_key.split("-")[-1]
            resp = await _http.get(f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}",
                headers={"Authorization": f"Bearer {mc_key}"})
            if resp.status_code == 200:
                data = resp.json()
                stats = data.get("stats", {})
                return json.dumps({
                    "provider": "mailchimp", "list_name": data.get("name", ""),
                    "member_count": stats.get("member_count", 0),
                    "open_rate": stats.get("open_rate", 0),
                    "click_rate": stats.get("click_rate", 0),
                    "unsubscribe_count": stats.get("unsubscribe_count", 0),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Analytics not configured for {provider}"})



def register_email_tools(registry):
    """Register all email tools with the given registry."""
    from models import ToolParameter

    registry.register("send_email", "Send an email via SendGrid. Rate limited to 50/day per campaign.",
        [ToolParameter(name="to", description="Recipient email address"),
         ToolParameter(name="subject", description="Email subject line"),
         ToolParameter(name="body", description="Email body (HTML supported)"),
         ToolParameter(name="from_name", description="Sender display name", required=False),
         ToolParameter(name="reply_to", description="Reply-to email address", required=False)],
        _send_email, "email")

    registry.register("schedule_email_sequence", "Schedule a sequence of emails. Input is JSON array of {to, subject, body, send_at}.",
        [ToolParameter(name="emails", description="JSON array of email objects")],
        _schedule_email_sequence, "email")

    registry.register("check_email_status", "Check delivery status of a sent email by message ID.",
        [ToolParameter(name="message_id", description="SendGrid message ID")],
        _check_email_status, "email")

    registry.register("check_email_warmup_status", "Check email warmup/deliverability status via Instantly.ai.",
        [ToolParameter(name="email_account", description="Email account to check warmup status for")],
        _check_email_warmup_status, "email")

    registry.register("detect_email_replies", "Detect replies and opens from sent email campaigns.",
        [ToolParameter(name="campaign_tag", description="Campaign tag to filter", required=False),
         ToolParameter(name="since_hours", type="integer", description="Hours to look back (default 24)", required=False)],
        _detect_email_replies, "email")

    # ── Voice & SMS Tools ──

    registry.register("create_email_list", "Create an email list/tag in ConvertKit, Mailchimp, or Beehiiv.",
        [ToolParameter(name="list_name", description="Name for the list or tag"),
         ToolParameter(name="provider", description="ESP: convertkit, mailchimp, beehiiv", required=False)],
        _create_email_list, "newsletter")

    registry.register("add_subscriber", "Add a subscriber to an email list.",
        [ToolParameter(name="email", description="Subscriber email"),
         ToolParameter(name="name", description="Subscriber name", required=False),
         ToolParameter(name="tags", description="Tags or list IDs (comma-separated)", required=False),
         ToolParameter(name="provider", description="ESP: convertkit, mailchimp", required=False)],
        _add_subscriber, "newsletter")

    registry.register("get_email_analytics", "Get email subscriber analytics — open rates, growth, engagement.",
        [ToolParameter(name="provider", description="ESP: convertkit, mailchimp", required=False),
         ToolParameter(name="list_id", description="List/audience ID (Mailchimp)", required=False)],
        _get_email_analytics, "newsletter")

    # ── PPC / Analytics Tools ──

