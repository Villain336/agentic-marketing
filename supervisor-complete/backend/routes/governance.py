"""Governance policy CRUD and evaluation endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from auth import get_user_id, validate_id
from governance import Policy, PolicyEngine, PolicyViolation, policy_engine, safe_eval

logger = logging.getLogger("omnios.routes.governance")

router = APIRouter(tags=["Governance"])


# ── Request / Response models ────────────────────────────────────────────────

class CreatePolicyRequest(BaseModel):
    name: str
    description: str = ""
    scope: str = "global"
    condition: str
    action: str = "block"
    enabled: bool = True


class UpdatePolicyRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    condition: Optional[str] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None


class EvaluateRequest(BaseModel):
    """Sample context to test policies against."""
    agent_id: str = ""
    tool_name: str = ""
    tool_input: dict = Field(default_factory=dict)
    campaign_id: str = ""
    user_id: str = ""
    spend_amount: float = 0.0
    hour: Optional[int] = None
    content: str = ""
    has_pii: Optional[bool] = None


VALID_ACTIONS = {"block", "warn", "require_approval", "log"}
VALID_SCOPE_PREFIXES = ("global", "agent:", "tool:", "campaign:")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/governance/policies")
async def list_policies(request: Request):
    """List all governance policies."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    policies = policy_engine.list_policies()
    return {
        "policies": [p.model_dump(mode="json") for p in policies],
        "count": len(policies),
    }


@router.post("/governance/policies")
async def create_policy(req: CreatePolicyRequest, request: Request):
    """Create a new governance policy."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    # Validate action
    if req.action not in VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action: {req.action}. Valid: {VALID_ACTIONS}")

    # Validate scope
    if not any(req.scope == prefix or req.scope.startswith(prefix)
               for prefix in VALID_SCOPE_PREFIXES):
        raise HTTPException(400, f"Invalid scope: {req.scope}. "
                            f"Must be 'global' or start with agent:, tool:, campaign:")

    # Validate condition syntax by parsing it
    try:
        safe_eval(req.condition, {
            "agent_id": "", "tool_name": "", "tool_input": {},
            "campaign_id": "", "user_id": "", "spend_amount": 0.0,
            "hour": 12, "has_pii": False, "content": "",
        })
    except ValueError as e:
        raise HTTPException(400, f"Invalid condition expression: {e}")
    except (KeyError, TypeError):
        pass  # Variables not in test context — that's fine

    policy = Policy(
        name=req.name,
        description=req.description,
        scope=req.scope,
        condition=req.condition,
        action=req.action,
        enabled=req.enabled,
        created_by=user_id,
    )

    policy_engine.add_policy(policy)
    logger.info(f"User {user_id[:8]}... created policy {policy.id}")

    return {"policy": policy.model_dump(mode="json")}


@router.put("/governance/policies/{policy_id}")
async def update_policy(policy_id: str, req: UpdatePolicyRequest, request: Request):
    """Update an existing governance policy."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(policy_id, "policy_id")

    existing = policy_engine.get_policy(policy_id)
    if not existing:
        raise HTTPException(404, "Policy not found")

    if req.action is not None and req.action not in VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action: {req.action}. Valid: {VALID_ACTIONS}")

    if req.scope is not None:
        if not any(req.scope == prefix or req.scope.startswith(prefix)
                   for prefix in VALID_SCOPE_PREFIXES):
            raise HTTPException(400, f"Invalid scope: {req.scope}")

    if req.condition is not None:
        try:
            safe_eval(req.condition, {
                "agent_id": "", "tool_name": "", "tool_input": {},
                "campaign_id": "", "user_id": "", "spend_amount": 0.0,
                "hour": 12, "has_pii": False, "content": "",
            })
        except ValueError as e:
            raise HTTPException(400, f"Invalid condition expression: {e}")
        except (KeyError, TypeError):
            pass

    # Apply updates
    if req.name is not None:
        existing.name = req.name
    if req.description is not None:
        existing.description = req.description
    if req.scope is not None:
        existing.scope = req.scope
    if req.condition is not None:
        existing.condition = req.condition
    if req.action is not None:
        existing.action = req.action
    if req.enabled is not None:
        existing.enabled = req.enabled

    policy_engine.add_policy(existing)
    return {"policy": existing.model_dump(mode="json")}


@router.delete("/governance/policies/{policy_id}")
async def delete_policy(policy_id: str, request: Request):
    """Remove a governance policy."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_id(policy_id, "policy_id")

    removed = policy_engine.remove_policy(policy_id)
    if not removed:
        raise HTTPException(404, "Policy not found")

    return {"id": policy_id, "status": "deleted"}


@router.post("/governance/evaluate")
async def evaluate_policies(req: EvaluateRequest, request: Request):
    """Test governance policies against a sample context.

    Useful for dry-running policies before enabling them.
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    context = req.model_dump(exclude_none=True)
    violations = policy_engine.evaluate(context)

    return {
        "violations": [v.model_dump() for v in violations],
        "count": len(violations),
        "blocked": any(v.action == "block" for v in violations),
        "requires_approval": any(v.action == "require_approval" for v in violations),
        "context_evaluated": {
            k: v for k, v in context.items()
            if k in ("agent_id", "tool_name", "campaign_id", "spend_amount", "hour")
        },
    }


@router.get("/governance/violations")
async def list_violations(request: Request, limit: int = 100, policy_id: str = ""):
    """List recent policy violations."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    limit = max(1, min(limit, 500))
    violations = policy_engine.list_violations(limit=limit, policy_id=policy_id)

    return {
        "violations": [v.model_dump() for v in violations],
        "count": len(violations),
    }
