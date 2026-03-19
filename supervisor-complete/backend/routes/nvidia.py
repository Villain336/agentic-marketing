"""NVIDIA GPU Infrastructure endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/nvidia", tags=["NVIDIA"])


@router.get("/gpus")
async def get_gpu_status():
    """GPU cluster status — available GPUs, utilization, allocations."""
    from nvidia_infra import gpu_cluster
    return await gpu_cluster.get_cluster_status()


@router.post("/gpus/allocate")
async def allocate_gpu(payload: dict):
    """Allocate a GPU for an agent task."""
    from nvidia_infra import gpu_cluster
    result = await gpu_cluster.allocate_gpu(
        payload.get("agent_id", ""), payload.get("gpu_type", ""),
        payload.get("vram_gb", 0),
    )
    if result:
        return result.model_dump()
    return {"error": "No GPU available"}


@router.post("/gpus/release")
async def release_gpu(payload: dict):
    """Release a GPU allocation."""
    from nvidia_infra import gpu_cluster
    ok = await gpu_cluster.release_gpu(payload.get("allocation_id", ""))
    return {"released": ok}


@router.get("/models")
async def list_nvidia_models():
    """List TensorRT-optimized and Triton-deployed models."""
    from nvidia_infra import tensorrt_optimizer, triton_server
    return {
        "tensorrt_engines": await tensorrt_optimizer.list_optimized_models(),
        "triton_models": await triton_server.list_deployed_models(),
    }


@router.post("/models/optimize")
async def optimize_model(payload: dict):
    """Optimize a model with TensorRT."""
    from nvidia_infra import tensorrt_optimizer
    engine = await tensorrt_optimizer.optimize_model(
        payload.get("model_path", ""), payload.get("precision", "fp16"),
        payload.get("target_gpu", ""), payload.get("model_name", ""),
    )
    return engine.model_dump()


@router.post("/models/deploy")
async def deploy_triton_model(payload: dict):
    """Deploy a model on Triton Inference Server."""
    from nvidia_infra import triton_server
    model = await triton_server.deploy_model(
        payload.get("model_name", ""), payload.get("model_path", ""),
        payload.get("instances", 1), payload.get("gpu_ids", []),
    )
    return model.model_dump()


@router.get("/digital-twins")
async def list_digital_twins():
    """List all digital twins."""
    from nvidia_infra import omniverse_connector
    return {"twins": [t.model_dump() for t in omniverse_connector._twins.values()]}


@router.post("/digital-twins")
async def create_digital_twin(payload: dict):
    """Create a digital twin."""
    from nvidia_infra import omniverse_connector
    twin = await omniverse_connector.create_digital_twin(
        payload.get("factory_config", {}), payload.get("name", ""),
    )
    return twin.model_dump()


@router.post("/digital-twins/{twin_id}/simulate")
async def simulate_twin(twin_id: str, payload: dict):
    """Run simulation on a digital twin."""
    from nvidia_infra import omniverse_connector
    return await omniverse_connector.simulate(twin_id, payload.get("scenario", {}))
