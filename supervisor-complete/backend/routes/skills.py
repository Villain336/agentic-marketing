"""SkillForge — self-writing skills endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from skillforge import skillforge
from providers import router as model_router

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.post("/create")
async def create_skill(request: Request):
    """Create a new self-authored skill."""
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
async def validate_skill(skill_id: str):
    """Validate a skill definition."""
    result = skillforge.validate_skill(skill_id)
    return result


@router.post("/{skill_id}/execute")
async def execute_skill(skill_id: str, request: Request):
    """Execute a validated skill."""
    body = await request.json()
    from tools import registry
    result = await skillforge.execute_skill(
        skill_id, body.get("inputs", {}),
        tool_registry=registry, llm_router=model_router,
    )
    return result.model_dump()


@router.post("/{skill_id}/register")
async def register_skill_as_tool(skill_id: str):
    """Register a validated skill as a callable tool."""
    from tools import registry
    success = skillforge.register_to_tool_registry(skill_id, registry)
    if not success:
        raise HTTPException(400, "Skill must be validated before registration")
    return {"registered": True, "skill_id": skill_id}


@router.post("/{skill_id}/publish")
async def publish_skill(skill_id: str):
    """Publish a skill to the marketplace."""
    success = skillforge.publish_skill(skill_id)
    if not success:
        raise HTTPException(400, "Skill must be validated before publishing")
    return {"published": True}


@router.get("")
async def list_skills(campaign_id: str = None):
    """List skills for a campaign or all skills."""
    skills = skillforge.list_skills(campaign_id=campaign_id)
    return {"skills": [s.model_dump() for s in skills]}
