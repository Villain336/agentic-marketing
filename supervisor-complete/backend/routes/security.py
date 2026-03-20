"""Enterprise Security — Compliance, Threat Modeling, Pen Testing, Trust Center."""
from __future__ import annotations
import json

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id

router = APIRouter(prefix="/security", tags=["Security"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.post("/scan")
async def run_security_scan(request: Request):
    """Execute automated security scan."""
    _require_auth(request)
    payload = await request.json()
    from tools import _run_security_scan
    result = json.loads(await _run_security_scan(
        payload.get("scan_type", "owasp_top_10"), payload.get("target", ""), payload.get("scope", "full"),
    ))
    return result


@router.post("/threat-model")
async def create_threat_model(request: Request):
    """Generate STRIDE threat model."""
    _require_auth(request)
    payload = await request.json()
    from tools import _threat_model
    result = json.loads(await _threat_model(
        payload["component"], payload.get("methodology", "stride"), payload.get("include_agent_threats", "true"),
    ))
    return result


@router.post("/compliance/audit")
async def run_compliance_audit(request: Request):
    """Check compliance posture against frameworks."""
    _require_auth(request)
    payload = await request.json()
    from tools import _compliance_audit
    result = json.loads(await _compliance_audit(payload.get("framework", "soc2"), payload.get("scope", "full")))
    return result


@router.get("/compliance/{framework}")
async def get_compliance_status(framework: str, request: Request):
    """Get compliance status for a specific framework."""
    _require_auth(request)
    from tools import _compliance_audit
    result = json.loads(await _compliance_audit(framework, "full"))
    return result


@router.post("/report")
async def generate_security_report(request: Request):
    """Generate security briefing."""
    _require_auth(request)
    payload = await request.json()
    from tools import _generate_security_report
    result = json.loads(await _generate_security_report(
        payload.get("report_type", "executive"), payload.get("period", "monthly"),
    ))
    return result


@router.post("/questionnaire")
async def answer_questionnaire(request: Request):
    """Auto-answer vendor security questionnaire."""
    _require_auth(request)
    payload = await request.json()
    from tools import _answer_security_questionnaire
    result = json.loads(await _answer_security_questionnaire(
        payload.get("questionnaire_type", "sig"), payload.get("custom_questions", ""),
    ))
    return result


@router.post("/red-team/{agent_id}")
async def red_team_agent(agent_id: str, request: Request):
    """Run adversarial tests against an agent."""
    _require_auth(request)
    payload = await request.json()
    from tools import _red_team_agent
    result = json.loads(await _red_team_agent(
        agent_id, payload.get("attack_type", "prompt_injection"), payload.get("intensity", "moderate"),
    ))
    return result


@router.get("/dependencies")
async def scan_dependencies(request: Request):
    """Scan dependencies for vulnerabilities and generate SBOM."""
    _require_auth(request)
    from tools import _scan_dependencies
    result = json.loads(await _scan_dependencies("full"))
    return result


@router.get("/dlp")
async def get_dlp_rules(request: Request):
    """Get DLP rules and enforcement stats."""
    _require_auth(request)
    from tools import _configure_dlp
    result = json.loads(await _configure_dlp("", "list"))
    return result


@router.post("/dlp")
async def update_dlp_rules(request: Request):
    """Update DLP rules."""
    _require_auth(request)
    payload = await request.json()
    from tools import _configure_dlp
    result = json.loads(await _configure_dlp(json.dumps(payload.get("rules", [])), payload.get("action", "add")))
    return result


@router.get("/encryption-keys")
async def get_encryption_key_status(request: Request):
    """Get encryption key management status."""
    _require_auth(request)
    from tools import _manage_encryption_keys
    result = json.loads(await _manage_encryption_keys("status"))
    return result


@router.post("/incidents")
async def manage_incidents(request: Request):
    """Manage security incidents."""
    _require_auth(request)
    payload = await request.json()
    from tools import _incident_response
    result = json.loads(await _incident_response(
        payload.get("action", "status"), payload.get("incident_id", ""), payload.get("severity", "medium"),
    ))
    return result


@router.get("/threat-intel")
async def get_threat_intel(request: Request):
    """Get current threat intelligence."""
    _require_auth(request)
    from tools import _monitor_threat_intel
    result = json.loads(await _monitor_threat_intel("relevant"))
    return result


@router.get("/trust")
async def get_trust_portal():
    """Public-facing security trust center."""
    from tools import _build_trust_portal
    result = json.loads(await _build_trust_portal("generate"))
    return result
