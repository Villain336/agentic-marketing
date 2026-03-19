"""WhatsApp integration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from whatsapp import whatsapp

router = APIRouter(tags=["WhatsApp"])


@router.get("/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification (GET challenge)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == whatsapp.verify_token:
        return int(challenge)
    raise HTTPException(403, "Verification failed")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive inbound WhatsApp messages and delivery receipts."""
    body = await request.json()
    messages = whatsapp.parse_webhook(body)
    for msg in messages:
        response = await whatsapp.process_inbound(msg)
        if response:
            await whatsapp.send_text(msg.phone, response)
    return {"status": "ok"}


@router.post("/whatsapp/send")
async def whatsapp_send(request: Request):
    """Send a WhatsApp message."""
    body = await request.json()
    msg_type = body.get("type", "text")
    if msg_type == "text":
        result = await whatsapp.send_text(body["phone"], body["text"])
    elif msg_type == "template":
        result = await whatsapp.send_template(body["phone"], body["template"],
                                               parameters=body.get("parameters"))
    elif msg_type == "buttons":
        result = await whatsapp.send_interactive_buttons(body["phone"], body["text"],
                                                          body.get("buttons", []))
    elif msg_type == "media":
        result = await whatsapp.send_media(body["phone"], body.get("media_type", "image"),
                                            body["media_url"], body.get("caption", ""))
    else:
        raise HTTPException(400, f"Unknown message type: {msg_type}")
    return result


@router.post("/whatsapp/briefing")
async def whatsapp_send_briefing(request: Request):
    """Send a daily briefing via WhatsApp."""
    body = await request.json()
    result = await whatsapp.send_daily_briefing(body["phone"], body.get("briefing", {}))
    return result


@router.post("/whatsapp/approval")
async def whatsapp_send_approval(request: Request):
    """Send an approval request via WhatsApp."""
    body = await request.json()
    result = await whatsapp.send_approval_request(body["phone"], body.get("approval", {}))
    return result


@router.get("/whatsapp/conversation/{phone}")
async def whatsapp_conversation(phone: str, limit: int = 50):
    """Get WhatsApp conversation history."""
    return {"messages": whatsapp.get_conversation(phone, limit)}
