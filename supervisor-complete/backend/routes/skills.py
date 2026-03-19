"""SkillForge — self-writing skills endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from skillforge import skillforge
from providers import router as model_router
from auth import get_user_id

router = APIRouter(prefix="/skills", tags=["Skills"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.post("/create")
async def create_skill(request: Request):
    """Create a new self-authored skill."""
    _require_auth(request)
    body = await request.json()
    try:
        skill = skillforge.create_skill(
            name=body["name"], description=body["description"],
            parameters=body.get("parameters", []),
            implementation_type=body.get("implementation_type", "api_chain"),
            implementation=body.get("implementation", {}),
            author_agent_id=body.get("agent_id", ""),
            campaign_id=body.get("campaign_id", ""),
            tags=body.get("tags", []),
        )
        return skill.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{skill_id}/validate")
async def validate_skill(skill_id: str, request: Request):
    """Validate a skill definition."""
    _require_auth(request)
    result = skillforge.validate_skill(skill_id)
    return result


@router.post("/{skill_id}/execute")
async def execute_skill(skill_id: str, request: Request):
    """Execute a validated skill."""
    _require_auth(request)
    body = await request.json()
    from tools import registry
    result = await skillforge.execute_skill(
        skill_id, body.get("inputs", {}),
        tool_registry=registry, llm_router=model_router,
    )
    return result.model_dump()


@router.post("/{skill_id}/register")
async def register_skill_as_tool(skill_id: str, request: Request):
    """Register a validated skill as a callable tool."""
    _require_auth(request)
    from tools import registry
    success = skillforge.register_to_tool_registry(skill_id, registry)
    if not success:
        raise HTTPException(400, "Skill must be validated before registration")
    return {"registered": True, "skill_id": skill_id}


@router.post("/{skill_id}/publish")
async def publish_skill(skill_id: str, request: Request):
    """Publish a skill to the marketplace."""
    _require_auth(request)
    success = skillforge.publish_skill(skill_id)
    if not success:
        raise HTTPException(400, "Skill must be validated before publishing")
    return {"published": True}


@router.get("")
async def list_skills(request: Request, campaign_id: str = None):
    """List skills for a campaign or all skills."""
    _require_auth(request)
    skills = skillforge.list_skills(campaign_id=campaign_id)
    return {"skills": [s.model_dump() for s in skills]}
