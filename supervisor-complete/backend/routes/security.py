"""Enterprise Security — Compliance, Threat Modeling, Pen Testing, Trust Center."""
from __future__ import annotations
import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/security", tags=["Security"])


@router.post("/scan")
async def run_security_scan(payload: dict):
    """Execute automated security scan."""
    from tools import _run_security_scan
    result = json.loads(await _run_security_scan(
        payload.get("scan_type", "owasp_top_10"), payload.get("target", ""), payload.get("scope", "full"),
    ))
    return result


@router.post("/threat-model")
async def create_threat_model(payload: dict):
    """Generate STRIDE threat model."""
    from tools import _threat_model
    result = json.loads(await _threat_model(
        payload["component"], payload.get("methodology", "stride"), payload.get("include_agent_threats", "true"),
    ))
    return result


@router.post("/compliance/audit")
async def run_compliance_audit(payload: dict):
    """Check compliance posture against frameworks."""
    from tools import _compliance_audit
    result = json.loads(await _compliance_audit(payload.get("framework", "soc2"), payload.get("scope", "full")))
    return result


@router.get("/compliance/{framework}")
async def get_compliance_status(framework: str):
    """Get compliance status for a specific framework."""
    from tools import _compliance_audit
    result = json.loads(await _compliance_audit(framework, "full"))
    return result


@router.post("/report")
async def generate_security_report(payload: dict):
    """Generate security briefing."""
    from tools import _generate_security_report
    result = json.loads(await _generate_security_report(
        payload.get("report_type", "executive"), payload.get("period", "monthly"),
    ))
    return result


@router.post("/questionnaire")
async def answer_questionnaire(payload: dict):
    """Auto-answer vendor security questionnaire."""
    from tools import _answer_security_questionnaire
    result = json.loads(await _answer_security_questionnaire(
        payload.get("questionnaire_type", "sig"), payload.get("custom_questions", ""),
    ))
    return result


@router.post("/red-team/{agent_id}")
async def red_team_agent(agent_id: str, payload: dict):
    """Run adversarial tests against an agent."""
    from tools import _red_team_agent
    result = json.loads(await _red_team_agent(
        agent_id, payload.get("attack_type", "prompt_injection"), payload.get("intensity", "moderate"),
    ))
    return result


@router.get("/dependencies")
async def scan_dependencies():
    """Scan dependencies for vulnerabilities and generate SBOM."""
    from tools import _scan_dependencies
    result = json.loads(await _scan_dependencies("full"))
    return result


@router.get("/dlp")
async def get_dlp_rules():
    """Get DLP rules and enforcement stats."""
    from tools import _configure_dlp
    result = json.loads(await _configure_dlp("", "list"))
    return result


@router.post("/dlp")
async def update_dlp_rules(payload: dict):
    """Update DLP rules."""
    from tools import _configure_dlp
    result = json.loads(await _configure_dlp(json.dumps(payload.get("rules", [])), payload.get("action", "add")))
    return result


@router.get("/encryption-keys")
async def get_encryption_key_status():
    """Get encryption key management status."""
    from tools import _manage_encryption_keys
    result = json.loads(await _manage_encryption_keys("status"))
    return result


@router.post("/incidents")
async def manage_incidents(payload: dict):
    """Manage security incidents."""
    from tools import _incident_response
    result = json.loads(await _incident_response(
        payload.get("action", "status"), payload.get("incident_id", ""), payload.get("severity", "medium"),
    ))
    return result


@router.get("/threat-intel")
async def get_threat_intel():
    """Get current threat intelligence."""
    from tools import _monitor_threat_intel
    result = json.loads(await _monitor_threat_intel("relevant"))
    return result


@router.get("/trust")
async def get_trust_portal():
    """Public-facing security trust center."""
    from tools import _build_trust_portal
    result = json.loads(await _build_trust_portal("generate"))
    return result
