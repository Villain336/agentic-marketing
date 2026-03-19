"""Wide research endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from wideresearch import wide_research
from providers import router as model_router

router = APIRouter(tags=["Research"])


@router.post("/research/wide")
async def create_wide_research(request: Request):
    """Create a wide research job with parallel sub-agents."""
    body = await request.json()
    job = wide_research.create_job(
        topic=body["topic"],
        campaign_id=body.get("campaign_id", ""),
        user_id=body.get("user_id", ""),
        strategy=body.get("strategy", "general"),
        max_parallel=body.get("max_parallel", 5),
        custom_queries=body.get("custom_queries"),
        targets=body.get("targets"),
    )
    return job.model_dump()


@router.post("/research/wide/{job_id}/execute")
async def execute_wide_research(job_id: str):
    """Execute a wide research job."""
    from tools import registry
    try:
        job = await wide_research.execute(job_id, llm_router=model_router, tool_registry=registry)
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/research/wide/{job_id}")
async def get_wide_research(job_id: str):
    """Get wide research job status and results."""
    job = wide_research.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    synthesis = wide_research.get_synthesis(job_id)
    result = job.model_dump()
    if synthesis:
        result["synthesis"] = synthesis.model_dump()
    return result


@router.get("/research/wide")
async def list_wide_research(campaign_id: str = None, user_id: str = None):
    """List wide research jobs."""
    jobs = wide_research.list_jobs(campaign_id, user_id)
    return {"jobs": [j.model_dump() for j in jobs]}


@router.get("/research/strategies")
async def list_research_strategies():
    """List available research decomposition strategies."""
    return {"strategies": wide_research.get_available_strategies()}
