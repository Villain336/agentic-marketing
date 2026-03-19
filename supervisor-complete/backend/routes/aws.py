"""AWS Infrastructure endpoints — EKS, SageMaker, IoT."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from auth import get_user_id

router = APIRouter(prefix="/aws", tags=["AWS"])


def _require_auth(request: Request) -> str:
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    return user_id


@router.get("/eks")
async def get_eks_status(request: Request):
    """EKS cluster metrics."""
    _require_auth(request)
    from aws_infra import eks_manager
    return await eks_manager.get_cluster_metrics()


@router.post("/eks/clusters")
async def create_eks_cluster(request: Request):
    """Create an EKS cluster."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import eks_manager
    return await eks_manager.create_cluster(
        payload.get("name", ""), payload.get("node_type", "m5.xlarge"),
        payload.get("gpu_nodes", 0),
    )


@router.post("/eks/workspaces")
async def deploy_workspace(request: Request):
    """Deploy an agent workspace on EKS."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import eks_manager
    return await eks_manager.deploy_agent_workspace(
        payload.get("cluster", ""), payload.get("agent_id", ""),
        payload.get("resources", {}),
    )


@router.get("/sagemaker/jobs")
async def list_sagemaker_jobs(request: Request):
    """List SageMaker training jobs."""
    _require_auth(request)
    from aws_infra import sagemaker_pipeline
    return {"jobs": list(sagemaker_pipeline._jobs.values())}


@router.post("/sagemaker/train")
async def create_training_job(request: Request):
    """Launch a SageMaker training job."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import sagemaker_pipeline
    return await sagemaker_pipeline.create_training_job(
        payload.get("dataset_s3", ""), payload.get("model_type", ""),
        payload.get("hyperparams", {}), payload.get("instance_type", "ml.g5.xlarge"),
    )


@router.get("/sagemaker/endpoints")
async def list_sagemaker_endpoints(request: Request):
    """List SageMaker endpoints."""
    _require_auth(request)
    from aws_infra import sagemaker_pipeline
    return {"endpoints": await sagemaker_pipeline.list_endpoints()}


@router.post("/sagemaker/deploy")
async def deploy_sagemaker_endpoint(request: Request):
    """Deploy a model as a SageMaker endpoint."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import sagemaker_pipeline
    return await sagemaker_pipeline.deploy_endpoint(
        payload.get("model_artifact", ""), payload.get("instance_type", "ml.g5.xlarge"),
        payload.get("auto_scaling", True),
    )


@router.get("/iot/devices")
async def list_iot_devices(request: Request, factory_id: str = ""):
    """List registered IoT devices."""
    _require_auth(request)
    from aws_infra import iot_core_manager
    return {"devices": await iot_core_manager.list_devices(factory_id)}


@router.post("/iot/devices")
async def register_iot_device(request: Request):
    """Register a factory floor device."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import iot_core_manager
    return await iot_core_manager.register_device(
        payload.get("device_id", ""), payload.get("device_type", ""),
        payload.get("factory_id", ""),
    )


@router.get("/iot/devices/{device_id}/telemetry")
async def get_device_telemetry(device_id: str, request: Request, metric: str = "", time_range: str = "1h"):
    """Get device telemetry data."""
    _require_auth(request)
    from aws_infra import iot_core_manager
    return await iot_core_manager.get_telemetry(device_id, metric, time_range)


@router.post("/iot/commands")
async def send_iot_command(request: Request):
    """Send a command to a factory device."""
    _require_auth(request)
    payload = await request.json()
    from aws_infra import iot_core_manager
    return await iot_core_manager.send_command(
        payload.get("device_id", ""), payload.get("command", {}),
    )
