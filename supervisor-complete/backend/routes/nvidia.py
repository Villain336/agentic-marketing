"""NVIDIA GPU Infrastructure endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id

router = APIRouter(prefix="/nvidia", tags=["NVIDIA"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.get("/gpus")
async def get_gpu_status(request: Request):
    """GPU cluster status — available GPUs, utilization, allocations."""
    _require_auth(request)
    from nvidia_infra import gpu_cluster
    return await gpu_cluster.get_cluster_status()


@router.post("/gpus/allocate")
async def allocate_gpu(request: Request):
    """Allocate a GPU for an agent task."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import gpu_cluster
    result = await gpu_cluster.allocate_gpu(
        payload.get("agent_id", ""), payload.get("gpu_type", ""),
        payload.get("vram_gb", 0),
    )
    if result:
        return result.model_dump()
    return {"error": "No GPU available"}


@router.post("/gpus/release")
async def release_gpu(request: Request):
    """Release a GPU allocation."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import gpu_cluster
    ok = await gpu_cluster.release_gpu(payload.get("allocation_id", ""))
    return {"released": ok}


@router.get("/models")
async def list_nvidia_models(request: Request):
    """List TensorRT-optimized and Triton-deployed models."""
    _require_auth(request)
    from nvidia_infra import tensorrt_optimizer, triton_server
    return {
        "tensorrt_engines": await tensorrt_optimizer.list_optimized_models(),
        "triton_models": await triton_server.list_deployed_models(),
    }


@router.post("/models/optimize")
async def optimize_model(request: Request):
    """Optimize a model with TensorRT."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import tensorrt_optimizer
    engine = await tensorrt_optimizer.optimize_model(
        payload.get("model_path", ""), payload.get("precision", "fp16"),
        payload.get("target_gpu", ""), payload.get("model_name", ""),
    )
    return engine.model_dump()


@router.post("/models/deploy")
async def deploy_triton_model(request: Request):
    """Deploy a model on Triton Inference Server."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import triton_server
    model = await triton_server.deploy_model(
        payload.get("model_name", ""), payload.get("model_path", ""),
        payload.get("instances", 1), payload.get("gpu_ids", []),
    )
    return model.model_dump()


@router.get("/digital-twins")
async def list_digital_twins(request: Request):
    """List all digital twins."""
    _require_auth(request)
    from nvidia_infra import omniverse_connector
    return {"twins": [t.model_dump() for t in omniverse_connector._twins.values()]}


@router.post("/digital-twins")
async def create_digital_twin(request: Request):
    """Create a digital twin."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import omniverse_connector
    twin = await omniverse_connector.create_digital_twin(
        payload.get("factory_config", {}), payload.get("name", ""),
    )
    return twin.model_dump()


@router.post("/digital-twins/{twin_id}/simulate")
async def simulate_twin(twin_id: str, request: Request):
    """Run simulation on a digital twin."""
    _require_auth(request)
    payload = await request.json()
    from nvidia_infra import omniverse_connector
    return await omniverse_connector.simulate(twin_id, payload.get("scenario", {}))
