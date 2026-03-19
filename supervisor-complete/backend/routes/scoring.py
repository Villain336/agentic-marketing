"""Campaign scores, lifecycle, A/B tests, dissolution."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from scoring import scorer
from lifecycle import lifecycle
from auth import get_user_id, validate_campaign_id
from store import store

router = APIRouter(tags=["Scoring & Lifecycle"])


@router.get("/campaign/{campaign_id}/scores")
async def get_campaign_scores(campaign_id: str, request: Request):
    """Get performance scores for all agents in a campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return scorer.score_all(campaign)


@router.get("/campaign/{campaign_id}/health")
async def campaign_health(campaign_id: str, request: Request):
    """Evaluate agent health across a campaign."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return lifecycle.evaluate_health(campaign)


@router.get("/campaign/{campaign_id}/lifecycle/recommendations")
async def lifecycle_recommendations(campaign_id: str, request: Request):
    """Get dissolution/A/B test recommendations for underperforming agents."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    validate_campaign_id(campaign_id)
    campaign = store.get_campaign(user_id, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return {"recommendations": lifecycle.recommend_dissolution(campaign)}


@router.post("/lifecycle/ab-test")
async def create_ab_test(request: Request):
    """Create an A/B test between agent variants."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    variants = body.get("variants", [])
    if not agent_id or len(variants) < 2:
        raise HTTPException(400, "Need agent_id and at least 2 variants")

    test = lifecycle.create_ab_test(
        agent_id=agent_id,
        variant_configs=variants,
        min_runs=body.get("min_runs", 3),
        auto_promote=body.get("auto_promote", True),
    )
    return test.to_dict()


@router.get("/lifecycle/ab-test/{test_id}")
async def get_ab_test(test_id: str):
    """Get A/B test status and results."""
    result = lifecycle.get_test(test_id)
    if not result:
        raise HTTPException(404, "Test not found")
    return result


@router.post("/lifecycle/ab-test/{test_id}/result")
async def record_ab_result(test_id: str, request: Request):
    """Record a variant run result."""
    body = await request.json()
    winner = lifecycle.record_test_result(
        test_id, body.get("variant_id", ""), body.get("score", 0),
    )
    return {"recorded": True, "winner_id": winner}


@router.get("/lifecycle/tests")
async def list_ab_tests(agent_id: str = ""):
    """List all A/B tests, optionally filtered by agent."""
    return {"tests": lifecycle.list_tests(agent_id)}


@router.post("/lifecycle/dissolve")
async def dissolve_agent(request: Request):
    """Dissolve an underperforming agent in a campaign."""
    body = await request.json()
    result = lifecycle.dissolve_agent(
        body.get("agent_id", ""), body.get("campaign_id", ""), body.get("reason", ""),
    )
    return result


@router.post("/lifecycle/promote")
async def promote_variant(request: Request):
    """Promote a winning A/B test variant to default."""
    body = await request.json()
    result = lifecycle.promote_variant(body.get("variant_id", ""), body.get("reason", ""))
    return result


@router.get("/lifecycle/log")
async def lifecycle_log(campaign_id: str = ""):
    """Get dissolution and promotion history."""
    return {
        "dissolutions": lifecycle.get_dissolution_log(campaign_id),
        "promotions": lifecycle.get_promotion_log(),
    }
