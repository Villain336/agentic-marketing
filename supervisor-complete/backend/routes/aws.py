"""AWS Infrastructure endpoints — EKS, SageMaker, IoT."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/aws", tags=["AWS"])


@router.get("/eks")
async def get_eks_status():
    """EKS cluster metrics."""
    from aws_infra import eks_manager
    return await eks_manager.get_cluster_metrics()


@router.post("/eks/clusters")
async def create_eks_cluster(payload: dict):
    """Create an EKS cluster."""
    from aws_infra import eks_manager
    return await eks_manager.create_cluster(
        payload.get("name", ""), payload.get("node_type", "m5.xlarge"),
        payload.get("gpu_nodes", 0),
    )


@router.post("/eks/workspaces")
async def deploy_workspace(payload: dict):
    """Deploy an agent workspace on EKS."""
    from aws_infra import eks_manager
    return await eks_manager.deploy_agent_workspace(
        payload.get("cluster", ""), payload.get("agent_id", ""),
        payload.get("resources", {}),
    )


@router.get("/sagemaker/jobs")
async def list_sagemaker_jobs():
    """List SageMaker training jobs."""
    from aws_infra import sagemaker_pipeline
    return {"jobs": list(sagemaker_pipeline._jobs.values())}


@router.post("/sagemaker/train")
async def create_training_job(payload: dict):
    """Launch a SageMaker training job."""
    from aws_infra import sagemaker_pipeline
    return await sagemaker_pipeline.create_training_job(
        payload.get("dataset_s3", ""), payload.get("model_type", ""),
        payload.get("hyperparams", {}), payload.get("instance_type", "ml.g5.xlarge"),
    )


@router.get("/sagemaker/endpoints")
async def list_sagemaker_endpoints():
    """List SageMaker endpoints."""
    from aws_infra import sagemaker_pipeline
    return {"endpoints": await sagemaker_pipeline.list_endpoints()}


@router.post("/sagemaker/deploy")
async def deploy_sagemaker_endpoint(payload: dict):
    """Deploy a model as a SageMaker endpoint."""
    from aws_infra import sagemaker_pipeline
    return await sagemaker_pipeline.deploy_endpoint(
        payload.get("model_artifact", ""), payload.get("instance_type", "ml.g5.xlarge"),
        payload.get("auto_scaling", True),
    )


@router.get("/iot/devices")
async def list_iot_devices(factory_id: str = ""):
    """List registered IoT devices."""
    from aws_infra import iot_core_manager
    return {"devices": await iot_core_manager.list_devices(factory_id)}


@router.post("/iot/devices")
async def register_iot_device(payload: dict):
    """Register a factory floor device."""
    from aws_infra import iot_core_manager
    return await iot_core_manager.register_device(
        payload.get("device_id", ""), payload.get("device_type", ""),
        payload.get("factory_id", ""),
    )


@router.get("/iot/devices/{device_id}/telemetry")
async def get_device_telemetry(device_id: str, metric: str = "", time_range: str = "1h"):
    """Get device telemetry data."""
    from aws_infra import iot_core_manager
    return await iot_core_manager.get_telemetry(device_id, metric, time_range)


@router.post("/iot/commands")
async def send_iot_command(payload: dict):
    """Send a command to a factory device."""
    from aws_infra import iot_core_manager
    return await iot_core_manager.send_command(
        payload.get("device_id", ""), payload.get("command", {}),
    )
