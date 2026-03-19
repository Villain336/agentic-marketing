"""
Bland AI, Vapi, Twilio voice calls, SMS, and LinkedIn messaging.
"""

from __future__ import annotations

import json
import base64

from config import settings
from tools.registry import _http, _http_long


async def _make_phone_call(to_number: str, script: str, voice: str = "nat",
                            max_duration_minutes: int = 5) -> str:
    """Make an AI voice call using Bland.ai. Falls back to Twilio for basic calling."""
    bland_key = getattr(settings, 'bland_api_key', '') or ""
    if bland_key:
        try:
            resp = await _http_long.post("https://api.bland.ai/v1/calls",
                headers={"Authorization": bland_key, "Content-Type": "application/json"},
                json={
                    "phone_number": to_number,
                    "task": script,
                    "voice": voice,
                    "max_duration": max_duration_minutes,
                    "wait_for_greeting": True,
                    "record": True,
                })
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_id": data.get("call_id", ""), "status": "initiated",
                                   "to": to_number, "provider": "bland.ai"})
            return json.dumps({"error": f"Bland.ai {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "bland.ai"})
    vapi_key = getattr(settings, 'vapi_api_key', '') or ""
    if vapi_key:
        try:
            resp = await _http_long.post("https://api.vapi.ai/call/phone",
                headers={"Authorization": f"Bearer {vapi_key}", "Content-Type": "application/json"},
                json={
                    "phoneNumberId": getattr(settings, 'vapi_phone_id', ''),
                    "customer": {"number": to_number},
                    "assistant": {
                        "firstMessage": script[:200],
                        "model": {"provider": "openai", "model": "gpt-4o-mini",
                                  "messages": [{"role": "system", "content": script}]},
                    },
                    "maxDurationSeconds": max_duration_minutes * 60,
                })
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_id": data.get("id", ""), "status": "initiated",
                                   "to": to_number, "provider": "vapi"})
            return json.dumps({"error": f"Vapi {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "vapi"})
    twilio_sid = getattr(settings, 'twilio_account_sid', '') or ""
    twilio_token = getattr(settings, 'twilio_auth_token', '') or ""
    if twilio_sid and twilio_token:
        try:
            from_number = getattr(settings, 'twilio_phone_number', '') or ""
            auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
            twiml = f'<Response><Say>{script[:500]}</Say></Response>'
            resp = await _http.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Calls.json",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"To": to_number, "From": from_number, "Twiml": twiml})
            if resp.status_code in (200, 201):
                data = resp.json()
                return json.dumps({"call_sid": data.get("sid", ""), "status": data.get("status", ""),
                                   "to": to_number, "provider": "twilio"})
            return json.dumps({"error": f"Twilio {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e), "provider": "twilio"})
    return json.dumps({"error": "No voice provider configured. Set BLAND_API_KEY, VAPI_API_KEY, or TWILIO_ACCOUNT_SID."})



async def _get_call_transcript(call_id: str, provider: str = "bland.ai") -> str:
    """Retrieve transcript and analysis from a completed AI call."""
    if provider == "bland.ai":
        bland_key = getattr(settings, 'bland_api_key', '') or ""
        if not bland_key:
            return json.dumps({"error": "Bland.ai not configured."})
        try:
            resp = await _http.get(f"https://api.bland.ai/v1/calls/{call_id}",
                headers={"Authorization": bland_key})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "call_id": call_id, "status": d.get("status", ""),
                    "duration": d.get("call_length", ""),
                    "transcript": d.get("concatenated_transcript", "")[:5000],
                    "summary": d.get("summary", ""),
                    "recording_url": d.get("recording_url", ""),
                    "answered": d.get("answered_by", "") != "voicemail",
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    elif provider == "vapi":
        vapi_key = getattr(settings, 'vapi_api_key', '') or ""
        if not vapi_key:
            return json.dumps({"error": "Vapi not configured."})
        try:
            resp = await _http.get(f"https://api.vapi.ai/call/{call_id}",
                headers={"Authorization": f"Bearer {vapi_key}"})
            if resp.status_code == 200:
                d = resp.json()
                return json.dumps({
                    "call_id": call_id, "status": d.get("status", ""),
                    "duration": d.get("endedAt", ""),
                    "transcript": d.get("transcript", "")[:5000],
                    "recording_url": d.get("recordingUrl", ""),
                })
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown provider: {provider}"})



async def _send_sms(to_number: str, message: str) -> str:
    """Send SMS via Twilio."""
    twilio_sid = getattr(settings, 'twilio_account_sid', '') or ""
    twilio_token = getattr(settings, 'twilio_auth_token', '') or ""
    if not twilio_sid or not twilio_token:
        return json.dumps({"error": "Twilio not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."})
    try:
        from_number = getattr(settings, 'twilio_phone_number', '') or ""
        auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
        resp = await _http.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"To": to_number, "From": from_number, "Body": message[:1600]})
        if resp.status_code in (200, 201):
            data = resp.json()
            return json.dumps({"sent": True, "sid": data.get("sid", ""), "to": to_number})
        return json.dumps({"sent": False, "error": f"Twilio {resp.status_code}: {resp.text[:500]}"})
    except Exception as e:
        return json.dumps({"sent": False, "error": str(e)})



async def _send_linkedin_message(profile_url: str, message: str) -> str:
    """Send LinkedIn message/connection request via Phantombuster or Dripify."""
    phantom_key = getattr(settings, 'phantombuster_api_key', '') or ""
    if phantom_key:
        try:
            resp = await _http.post("https://api.phantombuster.com/api/v2/agents/launch",
                headers={"X-Phantombuster-Key": phantom_key, "Content-Type": "application/json"},
                json={
                    "id": getattr(settings, 'phantombuster_linkedin_agent_id', ''),
                    "argument": json.dumps({
                        "profileUrl": profile_url,
                        "message": message[:300],
                    }),
                })
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({"queued": True, "container_id": data.get("containerId", ""),
                                   "profile": profile_url})
            return json.dumps({"error": f"Phantombuster {resp.status_code}: {resp.text[:500]}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "LinkedIn automation not configured. Set PHANTOMBUSTER_API_KEY.",
                       "draft": {"profile": profile_url, "message": message[:300]}})



def register_voice_tools(registry):
    """Register all voice tools with the given registry."""
    from models import ToolParameter

    registry.register("make_phone_call", "Make an AI voice call using Bland.ai, Vapi, or Twilio. For cold calls, follow-ups, demos.",
        [ToolParameter(name="to_number", description="Phone number to call (E.164 format)"),
         ToolParameter(name="script", description="Call script or AI agent instructions"),
         ToolParameter(name="voice", description="Voice name (default: nat)", required=False),
         ToolParameter(name="max_duration_minutes", type="integer", description="Max call length in minutes", required=False)],
        _make_phone_call, "voice")

    registry.register("get_call_transcript", "Get transcript and analysis from a completed AI call.",
        [ToolParameter(name="call_id", description="Call ID from make_phone_call"),
         ToolParameter(name="provider", description="Provider: bland.ai or vapi", required=False)],
        _get_call_transcript, "voice")

    registry.register("send_sms", "Send SMS text message via Twilio.",
        [ToolParameter(name="to_number", description="Recipient phone number (E.164 format)"),
         ToolParameter(name="message", description="SMS message text (max 1600 chars)")],
        _send_sms, "voice")

    registry.register("send_linkedin_message", "Send LinkedIn message/connection request via Phantombuster.",
        [ToolParameter(name="profile_url", description="LinkedIn profile URL"),
         ToolParameter(name="message", description="Message to send (max 300 chars)")],
        _send_linkedin_message, "voice")

    # ── Social Tools ──

