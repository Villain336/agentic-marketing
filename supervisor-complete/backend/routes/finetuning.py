"""Custom model fine-tuning endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from finetuning import training_collector, finetune_manager
from auth import get_user_id

router = APIRouter(prefix="/finetuning", tags=["Fine-tuning"])


@router.post("/dataset")
async def create_training_dataset(request: Request):
    """Create a training dataset from agent execution traces."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    ds = training_collector.create_dataset(
        user_id=user_id,
        name=body["name"],
        agent_ids=body.get("agent_ids", []),
        min_score=body.get("min_score", 0.7),
        description=body.get("description", ""),
    )
    return ds.model_dump()


@router.post("/dataset/{dataset_id}/build")
async def build_training_dataset(dataset_id: str, request: Request):
    """Build dataset from captured traces across campaigns."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    try:
        ds = training_collector.build_dataset(dataset_id, body.get("campaign_ids", []))
        return ds.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/datasets")
async def list_training_datasets(request: Request):
    """List training datasets for the authenticated user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    datasets = training_collector.list_datasets(user_id)
    return {"datasets": [d.model_dump() for d in datasets]}


@router.post("/job")
async def create_finetune_job(request: Request):
    """Create a fine-tuning job."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    body = await request.json()
    try:
        job = finetune_manager.create_job(
            user_id=user_id,
            dataset_id=body["dataset_id"],
            provider=body.get("provider", "openai"),
            base_model=body.get("base_model", ""),
            hyperparameters=body.get("hyperparameters"),
        )
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/job/{job_id}/submit")
async def submit_finetune_job(job_id: str, request: Request):
    """Submit a fine-tuning job to the provider."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    try:
        job = finetune_manager.submit_job(job_id)
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/jobs")
async def list_finetune_jobs(request: Request):
    """List fine-tuning jobs for the authenticated user."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    jobs = finetune_manager.list_jobs(user_id)
    return {"jobs": [j.model_dump() for j in jobs]}


@router.get("/models")
async def list_customer_models(request: Request):
    """List the authenticated user's fine-tuned models."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    models = finetune_manager.list_customer_models(user_id)
    return {"models": [m.model_dump() for m in models]}
