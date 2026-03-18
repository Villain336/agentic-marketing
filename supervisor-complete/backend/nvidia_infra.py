"""
Supervisor Backend — NVIDIA GPU Infrastructure
================================================
GPU cluster management, TensorRT optimization, Triton inference serving,
Omniverse digital twins, Isaac Sim robotics, and Metropolis vision AI.

Provides production-grade integration with NVIDIA's accelerated computing stack
for the Supervisor SaaS platform — enabling GPU-backed inference, factory
simulation, robotic policy training, and vision-based quality inspection.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx

from config import settings

logger = logging.getLogger("supervisor.nvidia")

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

NVIDIA_API_KEY = getattr(settings, "nvidia_api_key", "") or ""
NVIDIA_API_BASE = getattr(settings, "nvidia_api_base", "https://api.nvidia.com/v1") or "https://api.nvidia.com/v1"
TRITON_SERVER_URL = getattr(settings, "triton_server_url", "http://localhost:8001") or "http://localhost:8001"
OMNIVERSE_URL = getattr(settings, "omniverse_url", "http://localhost:8011") or "http://localhost:8011"
ISAAC_SIM_URL = getattr(settings, "isaac_sim_url", "http://localhost:8012") or "http://localhost:8012"
METROPOLIS_URL = getattr(settings, "metropolis_url", "http://localhost:8013") or "http://localhost:8013"

_DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _auth_headers() -> dict[str, str]:
    """Return authorization headers for NVIDIA API calls."""
    headers = {**_DEFAULT_HEADERS}
    if NVIDIA_API_KEY:
        headers["Authorization"] = f"Bearer {NVIDIA_API_KEY}"
    return headers


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════

class GPUType(str, Enum):
    A100 = "A100"
    H100 = "H100"
    L40S = "L40S"


class AllocationStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    FAILED = "failed"


class OptimizationPrecision(str, Enum):
    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"
    FP8 = "fp8"


class DeploymentStatus(str, Enum):
    LOADING = "loading"
    READY = "ready"
    UNLOADING = "unloading"
    STOPPED = "stopped"
    ERROR = "error"


class SimulationStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingStatus(str, Enum):
    QUEUED = "queued"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"


class InspectionSeverity(str, Enum):
    PASS = "pass"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class GPUInfo:
    """Single GPU device information."""
    gpu_id: str = field(default_factory=lambda: f"GPU-{uuid.uuid4().hex[:8].upper()}")
    gpu_type: GPUType = GPUType.A100
    vram_total_gb: int = 80
    vram_used_gb: float = 0.0
    utilization_pct: float = 0.0
    temperature_c: float = 42.0
    power_watts: float = 250.0
    allocated_to: str = ""
    cost_per_hour: float = 2.50
    healthy: bool = True

    def to_dict(self) -> dict:
        return {
            "gpu_id": self.gpu_id,
            "gpu_type": self.gpu_type.value,
            "vram_total_gb": self.vram_total_gb,
            "vram_used_gb": round(self.vram_used_gb, 1),
            "vram_free_gb": round(self.vram_total_gb - self.vram_used_gb, 1),
            "utilization_pct": round(self.utilization_pct, 1),
            "temperature_c": round(self.temperature_c, 1),
            "power_watts": round(self.power_watts, 1),
            "allocated_to": self.allocated_to,
            "cost_per_hour": self.cost_per_hour,
            "healthy": self.healthy,
        }


@dataclass
class GPUAllocation:
    """A reservation of a GPU for an agent workload."""
    allocation_id: str = field(default_factory=lambda: f"ALLOC-{uuid.uuid4().hex[:12].upper()}")
    agent_id: str = ""
    gpu_id: str = ""
    gpu_type: GPUType = GPUType.A100
    vram_reserved_gb: float = 0.0
    status: AllocationStatus = AllocationStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    released_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "allocation_id": self.allocation_id,
            "agent_id": self.agent_id,
            "gpu_id": self.gpu_id,
            "gpu_type": self.gpu_type.value,
            "vram_reserved_gb": self.vram_reserved_gb,
            "status": self.status.value,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "released_at": datetime.fromtimestamp(self.released_at).isoformat() if self.released_at else None,
            "duration_seconds": round((self.released_at or time.time()) - self.created_at, 1),
        }


@dataclass
class OptimizedModel:
    """A TensorRT-optimized model in the registry."""
    model_id: str = field(default_factory=lambda: f"TRT-{uuid.uuid4().hex[:12].upper()}")
    original_path: str = ""
    engine_path: str = ""
    precision: OptimizationPrecision = OptimizationPrecision.FP16
    target_gpu: GPUType = GPUType.A100
    status: str = "optimizing"
    optimization_time_s: float = 0.0
    original_size_mb: float = 0.0
    engine_size_mb: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "original_path": self.original_path,
            "engine_path": self.engine_path,
            "precision": self.precision.value,
            "target_gpu": self.target_gpu.value,
            "status": self.status,
            "optimization_time_s": round(self.optimization_time_s, 2),
            "original_size_mb": round(self.original_size_mb, 1),
            "engine_size_mb": round(self.engine_size_mb, 1),
            "size_reduction_pct": round(
                (1 - self.engine_size_mb / max(self.original_size_mb, 0.1)) * 100, 1
            ),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
        }


@dataclass
class TritonDeployment:
    """A model deployed on Triton Inference Server."""
    deployment_id: str = field(default_factory=lambda: f"TRITON-{uuid.uuid4().hex[:12].upper()}")
    model_name: str = ""
    model_path: str = ""
    instances: int = 1
    gpu_ids: list[str] = field(default_factory=list)
    status: DeploymentStatus = DeploymentStatus.LOADING
    max_batch_size: int = 32
    created_at: float = field(default_factory=time.time)
    requests_total: int = 0
    errors_total: int = 0

    def to_dict(self) -> dict:
        return {
            "deployment_id": self.deployment_id,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "instances": self.instances,
            "gpu_ids": self.gpu_ids,
            "status": self.status.value,
            "max_batch_size": self.max_batch_size,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "uptime_seconds": round(time.time() - self.created_at, 1),
        }


@dataclass
class DigitalTwin:
    """An Omniverse digital twin of a factory or environment."""
    twin_id: str = field(default_factory=lambda: f"TWIN-{uuid.uuid4().hex[:12].upper()}")
    name: str = ""
    factory_config: dict[str, Any] = field(default_factory=dict)
    status: SimulationStatus = SimulationStatus.CREATED
    last_iot_sync: float = 0.0
    sensor_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "twin_id": self.twin_id,
            "name": self.name,
            "factory_config": self.factory_config,
            "status": self.status.value,
            "sensor_count": self.sensor_count,
            "last_iot_sync": datetime.fromtimestamp(self.last_iot_sync).isoformat() if self.last_iot_sync else None,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "age_seconds": round(time.time() - self.created_at, 1),
        }


@dataclass
class RobotSimulation:
    """An Isaac Sim robot simulation environment."""
    sim_id: str = field(default_factory=lambda: f"ISIM-{uuid.uuid4().hex[:12].upper()}")
    robot_type: str = ""
    task: str = ""
    status: SimulationStatus = SimulationStatus.CREATED
    policies: dict[str, dict] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "sim_id": self.sim_id,
            "robot_type": self.robot_type,
            "task": self.task,
            "status": self.status.value,
            "policy_count": len(self.policies),
            "policies": list(self.policies.keys()),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
        }


@dataclass
class InspectionPipeline:
    """A Metropolis vision AI inspection pipeline."""
    pipeline_id: str = field(default_factory=lambda: f"INSP-{uuid.uuid4().hex[:12].upper()}")
    camera_config: dict[str, Any] = field(default_factory=dict)
    model_id: str = ""
    status: str = "active"
    total_inspections: int = 0
    defects_found: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        defect_rate = (self.defects_found / max(self.total_inspections, 1)) * 100
        return {
            "pipeline_id": self.pipeline_id,
            "camera_config": self.camera_config,
            "model_id": self.model_id,
            "status": self.status,
            "total_inspections": self.total_inspections,
            "defects_found": self.defects_found,
            "defect_rate_pct": round(defect_rate, 2),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GPU Cluster Management
# ═══════════════════════════════════════════════════════════════════════════════

class NvidiaGPUCluster:
    """
    Manages a pool of NVIDIA GPUs for agent workloads.
    Tracks allocations, utilization, cost, and health across A100/H100/L40S devices.
    """

    GPU_SPECS: dict[str, dict] = {
        "A100": {"vram_gb": 80, "cost_per_hour": 2.50, "tdp_watts": 400},
        "H100": {"vram_gb": 80, "cost_per_hour": 4.50, "tdp_watts": 700},
        "L40S": {"vram_gb": 48, "cost_per_hour": 1.80, "tdp_watts": 350},
    }

    def __init__(self):
        self._gpus: dict[str, GPUInfo] = {}
        self._allocations: dict[str, GPUAllocation] = {}
        self._client = httpx.AsyncClient(
            base_url=NVIDIA_API_BASE,
            headers=_auth_headers(),
            timeout=30.0,
        )

    async def list_gpus(self) -> list[dict]:
        """Fetch available GPUs with utilization, memory, and temperature data."""
        try:
            resp = await self._client.get("/gpu/cluster/devices")
            resp.raise_for_status()
            devices = resp.json().get("devices", [])
            for dev in devices:
                gpu_id = dev.get("id", f"GPU-{uuid.uuid4().hex[:8].upper()}")
                gpu_type = GPUType(dev.get("type", "A100"))
                specs = self.GPU_SPECS.get(gpu_type.value, self.GPU_SPECS["A100"])
                gpu = GPUInfo(
                    gpu_id=gpu_id,
                    gpu_type=gpu_type,
                    vram_total_gb=dev.get("vram_total_gb", specs["vram_gb"]),
                    vram_used_gb=dev.get("vram_used_gb", 0.0),
                    utilization_pct=dev.get("utilization_pct", 0.0),
                    temperature_c=dev.get("temperature_c", 40.0),
                    power_watts=dev.get("power_watts", specs["tdp_watts"] * 0.6),
                    allocated_to=dev.get("allocated_to", ""),
                    cost_per_hour=specs["cost_per_hour"],
                    healthy=dev.get("healthy", True),
                )
                self._gpus[gpu_id] = gpu
            logger.info(f"Refreshed GPU inventory: {len(self._gpus)} devices")
        except httpx.HTTPError as exc:
            logger.warning(f"GPU cluster API unavailable ({exc}), using cached inventory")

        return [gpu.to_dict() for gpu in self._gpus.values()]

    async def allocate_gpu(self, agent_id: str, gpu_type: str, vram_gb: float) -> dict:
        """Reserve a GPU for an agent workload."""
        target_type = GPUType(gpu_type)

        # Find a suitable GPU with enough free VRAM
        candidate: Optional[GPUInfo] = None
        for gpu in self._gpus.values():
            if gpu.gpu_type != target_type:
                continue
            if gpu.allocated_to:
                continue
            free_vram = gpu.vram_total_gb - gpu.vram_used_gb
            if free_vram >= vram_gb and gpu.healthy:
                candidate = gpu
                break

        if not candidate:
            # Attempt allocation via remote API
            try:
                resp = await self._client.post("/gpu/allocations", json={
                    "agent_id": agent_id,
                    "gpu_type": gpu_type,
                    "vram_gb": vram_gb,
                })
                resp.raise_for_status()
                data = resp.json()
                allocation = GPUAllocation(
                    allocation_id=data.get("allocation_id", f"ALLOC-{uuid.uuid4().hex[:12].upper()}"),
                    agent_id=agent_id,
                    gpu_id=data.get("gpu_id", ""),
                    gpu_type=target_type,
                    vram_reserved_gb=vram_gb,
                    status=AllocationStatus.ACTIVE,
                )
                self._allocations[allocation.allocation_id] = allocation
                logger.info(f"GPU allocated via API: {allocation.allocation_id} -> {allocation.gpu_id}")
                return allocation.to_dict()
            except httpx.HTTPError as exc:
                logger.error(f"Remote GPU allocation failed: {exc}")
                return {"error": f"No {gpu_type} GPU available with {vram_gb}GB free VRAM"}

        # Local allocation
        candidate.allocated_to = agent_id
        candidate.vram_used_gb += vram_gb

        allocation = GPUAllocation(
            agent_id=agent_id,
            gpu_id=candidate.gpu_id,
            gpu_type=target_type,
            vram_reserved_gb=vram_gb,
            status=AllocationStatus.ACTIVE,
        )
        self._allocations[allocation.allocation_id] = allocation

        logger.info(
            f"GPU allocated: {allocation.allocation_id} -> "
            f"{candidate.gpu_id} ({gpu_type}, {vram_gb}GB) for agent {agent_id}"
        )
        return allocation.to_dict()

    async def release_gpu(self, allocation_id: str) -> dict:
        """Release a GPU allocation back to the pool."""
        allocation = self._allocations.get(allocation_id)
        if not allocation:
            return {"error": f"Allocation {allocation_id} not found"}
        if allocation.status == AllocationStatus.RELEASED:
            return {"error": f"Allocation {allocation_id} already released"}

        allocation.status = AllocationStatus.RELEASED
        allocation.released_at = time.time()

        # Free the GPU locally
        gpu = self._gpus.get(allocation.gpu_id)
        if gpu:
            gpu.vram_used_gb = max(0.0, gpu.vram_used_gb - allocation.vram_reserved_gb)
            if gpu.allocated_to == allocation.agent_id:
                gpu.allocated_to = ""

        # Notify remote cluster
        try:
            await self._client.delete(f"/gpu/allocations/{allocation_id}")
        except httpx.HTTPError as exc:
            logger.warning(f"Remote release notification failed: {exc}")

        logger.info(f"GPU released: {allocation_id}")
        return allocation.to_dict()

    async def get_cluster_status(self) -> dict:
        """Dashboard overview of the entire GPU cluster."""
        gpus = list(self._gpus.values())
        active_allocs = [a for a in self._allocations.values() if a.status == AllocationStatus.ACTIVE]

        total_vram = sum(g.vram_total_gb for g in gpus)
        used_vram = sum(g.vram_used_gb for g in gpus)
        total_cost_per_hour = sum(g.cost_per_hour for g in gpus if g.allocated_to)

        return {
            "total_gpus": len(gpus),
            "gpus_by_type": {
                t.value: sum(1 for g in gpus if g.gpu_type == t)
                for t in GPUType
            },
            "allocated_gpus": sum(1 for g in gpus if g.allocated_to),
            "free_gpus": sum(1 for g in gpus if not g.allocated_to and g.healthy),
            "unhealthy_gpus": sum(1 for g in gpus if not g.healthy),
            "total_vram_gb": total_vram,
            "used_vram_gb": round(used_vram, 1),
            "free_vram_gb": round(total_vram - used_vram, 1),
            "avg_utilization_pct": round(
                sum(g.utilization_pct for g in gpus) / max(len(gpus), 1), 1
            ),
            "avg_temperature_c": round(
                sum(g.temperature_c for g in gpus) / max(len(gpus), 1), 1
            ),
            "total_power_watts": round(sum(g.power_watts for g in gpus), 0),
            "cost_per_hour_usd": round(total_cost_per_hour, 2),
            "active_allocations": len(active_allocs),
            "unique_agents": len(set(a.agent_id for a in active_allocs)),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TensorRT Model Optimization
# ═══════════════════════════════════════════════════════════════════════════════

class TensorRTOptimizer:
    """
    Converts models to TensorRT engines for maximum GPU inference throughput.
    Supports FP32, FP16, INT8, and FP8 precision modes across GPU architectures.
    """

    def __init__(self):
        self._models: dict[str, OptimizedModel] = {}
        self._client = httpx.AsyncClient(
            base_url=NVIDIA_API_BASE,
            headers=_auth_headers(),
            timeout=120.0,
        )

    async def optimize_model(self, model_path: str, precision: str = "fp16",
                              target_gpu: str = "A100") -> dict:
        """Submit a model for TensorRT optimization."""
        prec = OptimizationPrecision(precision)
        gpu = GPUType(target_gpu)

        model = OptimizedModel(
            original_path=model_path,
            precision=prec,
            target_gpu=gpu,
            status="optimizing",
        )
        self._models[model.model_id] = model

        try:
            resp = await self._client.post("/tensorrt/optimize", json={
                "model_id": model.model_id,
                "model_path": model_path,
                "precision": precision,
                "target_gpu": target_gpu,
                "calibration_data": None,
                "workspace_size_mb": 4096,
                "max_batch_size": 64,
            })
            resp.raise_for_status()
            data = resp.json()

            model.engine_path = data.get("engine_path", f"/engines/{model.model_id}.trt")
            model.optimization_time_s = data.get("optimization_time_s", 0.0)
            model.original_size_mb = data.get("original_size_mb", 0.0)
            model.engine_size_mb = data.get("engine_size_mb", 0.0)
            model.status = data.get("status", "ready")

            logger.info(
                f"Model optimized: {model.model_id} "
                f"({precision}/{target_gpu}) in {model.optimization_time_s:.1f}s"
            )
        except httpx.HTTPError as exc:
            model.status = "failed"
            logger.error(f"TensorRT optimization failed for {model_path}: {exc}")
            return {"error": str(exc), "model_id": model.model_id, "status": "failed"}

        return model.to_dict()

    async def benchmark_model(self, engine_path: str) -> dict:
        """Run inference benchmarks on an optimized TensorRT engine."""
        # Find the model by engine path
        model: Optional[OptimizedModel] = None
        for m in self._models.values():
            if m.engine_path == engine_path:
                model = m
                break

        try:
            resp = await self._client.post("/tensorrt/benchmark", json={
                "engine_path": engine_path,
                "warmup_iterations": 50,
                "benchmark_iterations": 1000,
                "batch_sizes": [1, 8, 16, 32, 64],
                "concurrency_levels": [1, 4, 8],
            })
            resp.raise_for_status()
            data = resp.json()

            result = {
                "engine_path": engine_path,
                "model_id": model.model_id if model else None,
                "precision": model.precision.value if model else "unknown",
                "target_gpu": model.target_gpu.value if model else "unknown",
                "latency_ms": {
                    "p50": data.get("p50_ms", 0.0),
                    "p95": data.get("p95_ms", 0.0),
                    "p99": data.get("p99_ms", 0.0),
                    "mean": data.get("mean_ms", 0.0),
                },
                "throughput": {
                    "inferences_per_second": data.get("inferences_per_second", 0),
                    "tokens_per_second": data.get("tokens_per_second", 0),
                },
                "memory_mb": {
                    "gpu_peak": data.get("gpu_peak_mb", 0.0),
                    "gpu_steady": data.get("gpu_steady_mb", 0.0),
                },
                "batch_scaling": data.get("batch_scaling", {}),
            }
            logger.info(
                f"Benchmark complete: {engine_path} — "
                f"p50={result['latency_ms']['p50']:.1f}ms, "
                f"{result['throughput']['inferences_per_second']} inf/s"
            )
            return result

        except httpx.HTTPError as exc:
            logger.error(f"Benchmark failed for {engine_path}: {exc}")
            return {"error": str(exc), "engine_path": engine_path}

    def list_optimized_models(self) -> list[dict]:
        """Return all models in the TensorRT optimization registry."""
        return [m.to_dict() for m in self._models.values()]


# ═══════════════════════════════════════════════════════════════════════════════
# Triton Inference Server
# ═══════════════════════════════════════════════════════════════════════════════

class TritonServer:
    """
    Manages model deployments on NVIDIA Triton Inference Server.
    Handles dynamic loading/unloading, scaling, and real-time inference.
    """

    def __init__(self):
        self._deployments: dict[str, TritonDeployment] = {}
        self._client = httpx.AsyncClient(
            base_url=TRITON_SERVER_URL,
            headers=_DEFAULT_HEADERS,
            timeout=60.0,
        )

    async def deploy_model(self, model_name: str, model_path: str,
                            instances: int = 1, gpu_ids: list[str] | None = None) -> dict:
        """Deploy a model onto Triton Inference Server."""
        gpu_ids = gpu_ids or []

        deployment = TritonDeployment(
            model_name=model_name,
            model_path=model_path,
            instances=instances,
            gpu_ids=gpu_ids,
            status=DeploymentStatus.LOADING,
        )
        self._deployments[model_name] = deployment

        try:
            resp = await self._client.post("/v2/repository/models/load", json={
                "model_name": model_name,
                "parameters": {
                    "model_path": model_path,
                    "instance_count": str(instances),
                    "gpu_device_ids": ",".join(gpu_ids) if gpu_ids else "0",
                    "max_batch_size": str(deployment.max_batch_size),
                    "dynamic_batching": "true",
                    "preferred_batch_sizes": "4,8,16",
                    "max_queue_delay_microseconds": "100",
                },
            })
            resp.raise_for_status()

            deployment.status = DeploymentStatus.READY
            logger.info(
                f"Model deployed on Triton: {model_name} "
                f"({instances} instances on GPUs {gpu_ids})"
            )
        except httpx.HTTPError as exc:
            deployment.status = DeploymentStatus.ERROR
            logger.error(f"Triton deployment failed for {model_name}: {exc}")
            return {"error": str(exc), "model_name": model_name, "status": "error"}

        return deployment.to_dict()

    async def undeploy_model(self, model_name: str) -> dict:
        """Remove a model from Triton Inference Server."""
        deployment = self._deployments.get(model_name)
        if not deployment:
            return {"error": f"Model {model_name} not found in deployments"}

        deployment.status = DeploymentStatus.UNLOADING

        try:
            resp = await self._client.post("/v2/repository/models/unload", json={
                "model_name": model_name,
            })
            resp.raise_for_status()
            deployment.status = DeploymentStatus.STOPPED
            logger.info(f"Model undeployed from Triton: {model_name}")
        except httpx.HTTPError as exc:
            deployment.status = DeploymentStatus.ERROR
            logger.error(f"Triton undeploy failed for {model_name}: {exc}")
            return {"error": str(exc), "model_name": model_name}

        return deployment.to_dict()

    async def get_inference_metrics(self, model_name: str) -> dict:
        """Retrieve real-time inference metrics for a deployed model."""
        deployment = self._deployments.get(model_name)
        if not deployment:
            return {"error": f"Model {model_name} not found in deployments"}

        try:
            resp = await self._client.get(f"/v2/models/{model_name}/stats")
            resp.raise_for_status()
            stats = resp.json()

            inference_stats = stats.get("model_stats", [{}])[0] if stats.get("model_stats") else {}
            infer_stats = inference_stats.get("inference_stats", {})

            metrics = {
                "model_name": model_name,
                "deployment_id": deployment.deployment_id,
                "status": deployment.status.value,
                "latency_ms": {
                    "p50": infer_stats.get("queue_ns", {}).get("p50", 0) / 1e6,
                    "p95": infer_stats.get("compute_infer_ns", {}).get("p95", 0) / 1e6,
                    "p99": infer_stats.get("compute_infer_ns", {}).get("p99", 0) / 1e6,
                },
                "throughput": {
                    "requests_per_second": infer_stats.get("success", {}).get("count", 0)
                    / max(time.time() - deployment.created_at, 1),
                    "total_requests": deployment.requests_total,
                    "total_errors": deployment.errors_total,
                },
                "batch_statistics": infer_stats.get("batch_stats", {}),
                "gpu_utilization": infer_stats.get("gpu_utilization", {}),
                "uptime_seconds": round(time.time() - deployment.created_at, 1),
            }
            return metrics

        except httpx.HTTPError as exc:
            logger.warning(f"Failed to fetch Triton metrics for {model_name}: {exc}")
            return {
                "model_name": model_name,
                "status": deployment.status.value,
                "latency_ms": {"p50": 0, "p95": 0, "p99": 0},
                "throughput": {
                    "requests_per_second": 0,
                    "total_requests": deployment.requests_total,
                    "total_errors": deployment.errors_total,
                },
                "error": f"Metrics unavailable: {exc}",
            }

    async def infer(self, model_name: str, inputs: dict[str, Any]) -> dict:
        """Run inference on a deployed Triton model."""
        deployment = self._deployments.get(model_name)
        if not deployment:
            return {"error": f"Model {model_name} not found in deployments"}
        if deployment.status != DeploymentStatus.READY:
            return {"error": f"Model {model_name} is {deployment.status.value}, not ready"}

        request_id = f"REQ-{uuid.uuid4().hex[:12].upper()}"
        start_time = time.time()

        try:
            # Build Triton V2 inference request
            triton_inputs = []
            for name, data in inputs.items():
                triton_inputs.append({
                    "name": name,
                    "shape": data.get("shape", [1]),
                    "datatype": data.get("datatype", "FP32"),
                    "data": data.get("data", []),
                })

            resp = await self._client.post(f"/v2/models/{model_name}/infer", json={
                "id": request_id,
                "inputs": triton_inputs,
            })
            resp.raise_for_status()
            result = resp.json()

            elapsed_ms = (time.time() - start_time) * 1000
            deployment.requests_total += 1

            return {
                "request_id": request_id,
                "model_name": model_name,
                "outputs": result.get("outputs", []),
                "latency_ms": round(elapsed_ms, 2),
                "model_version": result.get("model_version", "1"),
            }

        except httpx.HTTPError as exc:
            deployment.errors_total += 1
            logger.error(f"Inference failed on {model_name}: {exc}")
            return {"error": str(exc), "request_id": request_id, "model_name": model_name}

    def list_deployed_models(self) -> list[dict]:
        """Return all models currently managed by this Triton instance."""
        return [d.to_dict() for d in self._deployments.values()]


# ═══════════════════════════════════════════════════════════════════════════════
# Omniverse Digital Twin
# ═══════════════════════════════════════════════════════════════════════════════

class OmniverseConnector:
    """
    Creates and manages NVIDIA Omniverse digital twins for factory simulation.
    Supports live IoT synchronization and USD/glTF/video export.
    """

    def __init__(self):
        self._twins: dict[str, DigitalTwin] = {}
        self._client = httpx.AsyncClient(
            base_url=OMNIVERSE_URL,
            headers=_auth_headers(),
            timeout=90.0,
        )

    async def create_digital_twin(self, factory_config: dict[str, Any]) -> dict:
        """Create a new digital twin from a factory configuration."""
        twin = DigitalTwin(
            name=factory_config.get("name", "Unnamed Factory"),
            factory_config=factory_config,
            sensor_count=len(factory_config.get("sensors", [])),
        )
        self._twins[twin.twin_id] = twin

        try:
            resp = await self._client.post("/omniverse/twins", json={
                "twin_id": twin.twin_id,
                "name": twin.name,
                "layout": factory_config.get("layout", {}),
                "machines": factory_config.get("machines", []),
                "conveyors": factory_config.get("conveyors", []),
                "sensors": factory_config.get("sensors", []),
                "physics": factory_config.get("physics", {"gravity": True, "collision": True}),
                "lighting": factory_config.get("lighting", "industrial_standard"),
                "scale": factory_config.get("scale", 1.0),
            })
            resp.raise_for_status()
            data = resp.json()

            twin.status = SimulationStatus(data.get("status", "created"))
            logger.info(f"Digital twin created: {twin.twin_id} — {twin.name}")
        except httpx.HTTPError as exc:
            twin.status = SimulationStatus.FAILED
            logger.error(f"Digital twin creation failed: {exc}")
            return {"error": str(exc), "twin_id": twin.twin_id}

        return twin.to_dict()

    async def simulate(self, twin_id: str, scenario: dict[str, Any]) -> dict:
        """Run a simulation scenario on a digital twin."""
        twin = self._twins.get(twin_id)
        if not twin:
            return {"error": f"Digital twin {twin_id} not found"}

        twin.status = SimulationStatus.RUNNING
        sim_run_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"

        try:
            resp = await self._client.post(f"/omniverse/twins/{twin_id}/simulate", json={
                "run_id": sim_run_id,
                "scenario": scenario.get("name", "default"),
                "duration_seconds": scenario.get("duration_seconds", 3600),
                "speed_multiplier": scenario.get("speed_multiplier", 10.0),
                "variables": scenario.get("variables", {}),
                "failure_injection": scenario.get("failure_injection", {}),
                "record_metrics": True,
            })
            resp.raise_for_status()
            data = resp.json()

            twin.status = SimulationStatus.COMPLETED

            result = {
                "twin_id": twin_id,
                "run_id": sim_run_id,
                "scenario": scenario.get("name", "default"),
                "status": "completed",
                "throughput": {
                    "units_per_hour": data.get("units_per_hour", 0),
                    "cycle_time_seconds": data.get("cycle_time_seconds", 0.0),
                    "oee_pct": data.get("oee_pct", 0.0),
                },
                "bottlenecks": data.get("bottlenecks", []),
                "energy_kwh": data.get("energy_kwh", 0.0),
                "idle_time_pct": data.get("idle_time_pct", 0.0),
                "recommendations": data.get("recommendations", []),
                "duration_simulated_s": scenario.get("duration_seconds", 3600),
                "wall_clock_s": data.get("wall_clock_seconds", 0.0),
            }
            logger.info(f"Simulation completed: {sim_run_id} on twin {twin_id}")
            return result

        except httpx.HTTPError as exc:
            twin.status = SimulationStatus.FAILED
            logger.error(f"Simulation failed on twin {twin_id}: {exc}")
            return {"error": str(exc), "twin_id": twin_id, "run_id": sim_run_id}

    async def update_twin_from_iot(self, twin_id: str, sensor_data: list[dict]) -> dict:
        """Synchronize a digital twin with live IoT sensor readings."""
        twin = self._twins.get(twin_id)
        if not twin:
            return {"error": f"Digital twin {twin_id} not found"}

        try:
            resp = await self._client.put(f"/omniverse/twins/{twin_id}/iot", json={
                "sensors": sensor_data,
                "timestamp": datetime.utcnow().isoformat(),
                "sync_mode": "live",
            })
            resp.raise_for_status()
            data = resp.json()

            twin.last_iot_sync = time.time()
            twin.sensor_count = len(sensor_data)

            return {
                "twin_id": twin_id,
                "sensors_updated": data.get("sensors_updated", len(sensor_data)),
                "sync_timestamp": datetime.fromtimestamp(twin.last_iot_sync).isoformat(),
                "drift_detected": data.get("drift_detected", False),
                "anomalies": data.get("anomalies", []),
            }
        except httpx.HTTPError as exc:
            logger.error(f"IoT sync failed for twin {twin_id}: {exc}")
            return {"error": str(exc), "twin_id": twin_id}

    async def export_visualization(self, twin_id: str, format: str = "usd") -> dict:
        """Export a digital twin visualization in USD, glTF, or video format."""
        twin = self._twins.get(twin_id)
        if not twin:
            return {"error": f"Digital twin {twin_id} not found"}

        export_id = f"EXP-{uuid.uuid4().hex[:12].upper()}"
        valid_formats = {"usd", "gltf", "video"}
        if format not in valid_formats:
            return {"error": f"Invalid format '{format}'. Supported: {', '.join(valid_formats)}"}

        try:
            resp = await self._client.post(f"/omniverse/twins/{twin_id}/export", json={
                "export_id": export_id,
                "format": format,
                "quality": "high",
                "include_physics": format != "video",
                "include_materials": True,
                "resolution": "3840x2160" if format == "video" else None,
                "fps": 60 if format == "video" else None,
            })
            resp.raise_for_status()
            data = resp.json()

            extensions = {"usd": ".usd", "gltf": ".glb", "video": ".mp4"}
            return {
                "twin_id": twin_id,
                "export_id": export_id,
                "format": format,
                "file_path": data.get("file_path", f"/exports/{twin_id}{extensions[format]}"),
                "file_size_mb": data.get("file_size_mb", 0.0),
                "download_url": data.get("download_url", ""),
                "status": "completed",
            }
        except httpx.HTTPError as exc:
            logger.error(f"Export failed for twin {twin_id}: {exc}")
            return {"error": str(exc), "twin_id": twin_id, "export_id": export_id}


# ═══════════════════════════════════════════════════════════════════════════════
# Isaac Sim Robotics
# ═══════════════════════════════════════════════════════════════════════════════

class IsaacSimConnector:
    """
    NVIDIA Isaac Sim integration for robot simulation, RL policy training,
    validation, and deployment to physical hardware.
    """

    def __init__(self):
        self._simulations: dict[str, RobotSimulation] = {}
        self._policies: dict[str, dict] = {}
        self._client = httpx.AsyncClient(
            base_url=ISAAC_SIM_URL,
            headers=_auth_headers(),
            timeout=120.0,
        )

    async def create_robot_sim(self, robot_type: str, task: str) -> dict:
        """Create a new robot simulation environment."""
        sim = RobotSimulation(
            robot_type=robot_type,
            task=task,
            status=SimulationStatus.CREATED,
        )
        self._simulations[sim.sim_id] = sim

        try:
            resp = await self._client.post("/isaac/simulations", json={
                "sim_id": sim.sim_id,
                "robot_type": robot_type,
                "task": task,
                "physics_dt": 1.0 / 120.0,
                "rendering_dt": 1.0 / 60.0,
                "domain_randomization": True,
                "ground_plane": True,
                "enable_sensors": True,
            })
            resp.raise_for_status()
            data = resp.json()

            sim.status = SimulationStatus(data.get("status", "created"))
            logger.info(f"Robot simulation created: {sim.sim_id} — {robot_type} / {task}")
        except httpx.HTTPError as exc:
            sim.status = SimulationStatus.FAILED
            logger.error(f"Isaac Sim creation failed: {exc}")
            return {"error": str(exc), "sim_id": sim.sim_id}

        return sim.to_dict()

    async def train_robot_policy(self, sim_id: str, algorithm: str = "PPO",
                                  episodes: int = 10000) -> dict:
        """Train a reinforcement learning policy in the simulation."""
        sim = self._simulations.get(sim_id)
        if not sim:
            return {"error": f"Simulation {sim_id} not found"}

        policy_id = f"POL-{uuid.uuid4().hex[:12].upper()}"
        sim.status = SimulationStatus.RUNNING

        try:
            resp = await self._client.post(f"/isaac/simulations/{sim_id}/train", json={
                "policy_id": policy_id,
                "algorithm": algorithm,
                "episodes": episodes,
                "parallel_envs": 4096,
                "learning_rate": 3e-4,
                "gamma": 0.99,
                "clip_range": 0.2,
                "entropy_coefficient": 0.01,
                "checkpoint_frequency": max(episodes // 10, 100),
                "early_stopping": True,
                "early_stopping_patience": 500,
            })
            resp.raise_for_status()
            data = resp.json()

            policy_data = {
                "policy_id": policy_id,
                "sim_id": sim_id,
                "algorithm": algorithm,
                "episodes_trained": data.get("episodes_trained", episodes),
                "final_reward": data.get("final_reward", 0.0),
                "convergence_episode": data.get("convergence_episode", 0),
                "training_time_s": data.get("training_time_s", 0.0),
                "status": TrainingStatus.COMPLETED.value,
                "checkpoints": data.get("checkpoints", []),
                "reward_curve": data.get("reward_curve", []),
            }
            sim.policies[policy_id] = policy_data
            self._policies[policy_id] = policy_data
            sim.status = SimulationStatus.COMPLETED

            logger.info(
                f"Policy trained: {policy_id} — {algorithm}, "
                f"{policy_data['episodes_trained']} episodes, "
                f"reward={policy_data['final_reward']:.2f}"
            )
            return policy_data

        except httpx.HTTPError as exc:
            sim.status = SimulationStatus.FAILED
            logger.error(f"Policy training failed for sim {sim_id}: {exc}")
            return {
                "error": str(exc),
                "policy_id": policy_id,
                "sim_id": sim_id,
                "status": TrainingStatus.FAILED.value,
            }

    async def validate_policy(self, sim_id: str, policy_id: str,
                               test_scenarios: list[dict]) -> dict:
        """Validate a trained policy against test scenarios before deployment."""
        sim = self._simulations.get(sim_id)
        if not sim:
            return {"error": f"Simulation {sim_id} not found"}
        if policy_id not in self._policies:
            return {"error": f"Policy {policy_id} not found"}

        try:
            resp = await self._client.post(
                f"/isaac/simulations/{sim_id}/validate",
                json={
                    "policy_id": policy_id,
                    "test_scenarios": test_scenarios,
                    "runs_per_scenario": 100,
                    "collect_video": True,
                    "safety_checks": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = {
                "policy_id": policy_id,
                "sim_id": sim_id,
                "scenarios_tested": len(test_scenarios),
                "overall_success_rate": data.get("overall_success_rate", 0.0),
                "scenario_results": data.get("scenario_results", []),
                "safety_violations": data.get("safety_violations", 0),
                "collision_count": data.get("collision_count", 0),
                "avg_completion_time_s": data.get("avg_completion_time_s", 0.0),
                "ready_for_deployment": data.get("ready_for_deployment", False),
                "video_urls": data.get("video_urls", []),
            }
            logger.info(
                f"Policy validated: {policy_id} — "
                f"success={results['overall_success_rate']:.1%}, "
                f"safety_violations={results['safety_violations']}"
            )
            return results

        except httpx.HTTPError as exc:
            logger.error(f"Policy validation failed: {exc}")
            return {"error": str(exc), "policy_id": policy_id, "sim_id": sim_id}

    async def export_policy(self, policy_id: str, target_hardware: str) -> dict:
        """Export a trained policy for deployment on physical robot hardware."""
        policy = self._policies.get(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        export_id = f"PEXP-{uuid.uuid4().hex[:12].upper()}"

        try:
            resp = await self._client.post(f"/isaac/policies/{policy_id}/export", json={
                "export_id": export_id,
                "target_hardware": target_hardware,
                "optimization": "tensorrt",
                "real_time_constraints": True,
                "safety_wrapper": True,
                "include_fallback_controller": True,
            })
            resp.raise_for_status()
            data = resp.json()

            return {
                "export_id": export_id,
                "policy_id": policy_id,
                "target_hardware": target_hardware,
                "file_path": data.get("file_path", f"/policies/{policy_id}_{target_hardware}.onnx"),
                "file_size_mb": data.get("file_size_mb", 0.0),
                "inference_time_ms": data.get("inference_time_ms", 0.0),
                "compatible": data.get("compatible", True),
                "safety_certified": data.get("safety_certified", False),
                "status": "exported",
            }
        except httpx.HTTPError as exc:
            logger.error(f"Policy export failed: {exc}")
            return {"error": str(exc), "policy_id": policy_id, "export_id": export_id}


# ═══════════════════════════════════════════════════════════════════════════════
# Metropolis Vision AI
# ═══════════════════════════════════════════════════════════════════════════════

class MetropolisConnector:
    """
    NVIDIA Metropolis integration for factory vision AI.
    Manages inspection pipelines, defect detection, analytics, and model retraining.
    """

    def __init__(self):
        self._pipelines: dict[str, InspectionPipeline] = {}
        self._client = httpx.AsyncClient(
            base_url=METROPOLIS_URL,
            headers=_auth_headers(),
            timeout=60.0,
        )

    async def create_inspection_pipeline(self, camera_config: dict[str, Any],
                                          model_id: str) -> dict:
        """Create a new vision inspection pipeline for quality control."""
        pipeline = InspectionPipeline(
            camera_config=camera_config,
            model_id=model_id,
        )
        self._pipelines[pipeline.pipeline_id] = pipeline

        try:
            resp = await self._client.post("/metropolis/pipelines", json={
                "pipeline_id": pipeline.pipeline_id,
                "camera": {
                    "stream_url": camera_config.get("stream_url", ""),
                    "resolution": camera_config.get("resolution", "1920x1080"),
                    "fps": camera_config.get("fps", 30),
                    "codec": camera_config.get("codec", "H.264"),
                },
                "model_id": model_id,
                "inference_mode": "continuous",
                "confidence_threshold": 0.85,
                "nms_threshold": 0.45,
                "alert_on_defect": True,
                "save_detections": True,
            })
            resp.raise_for_status()
            logger.info(f"Inspection pipeline created: {pipeline.pipeline_id}")
        except httpx.HTTPError as exc:
            pipeline.status = "error"
            logger.error(f"Pipeline creation failed: {exc}")
            return {"error": str(exc), "pipeline_id": pipeline.pipeline_id}

        return pipeline.to_dict()

    async def run_inspection(self, pipeline_id: str, image_b64: str) -> dict:
        """Run a single inspection on an image through the pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return {"error": f"Pipeline {pipeline_id} not found"}

        inspection_id = f"INS-{uuid.uuid4().hex[:12].upper()}"

        try:
            resp = await self._client.post(
                f"/metropolis/pipelines/{pipeline_id}/inspect",
                json={
                    "inspection_id": inspection_id,
                    "image": image_b64,
                    "return_annotated": True,
                    "return_heatmap": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            detections = data.get("detections", [])
            has_defects = len(detections) > 0

            pipeline.total_inspections += 1
            if has_defects:
                pipeline.defects_found += 1

            max_severity = InspectionSeverity.PASS
            for det in detections:
                sev = InspectionSeverity(det.get("severity", "minor"))
                if list(InspectionSeverity).index(sev) > list(InspectionSeverity).index(max_severity):
                    max_severity = sev

            result = {
                "inspection_id": inspection_id,
                "pipeline_id": pipeline_id,
                "passed": not has_defects,
                "severity": max_severity.value,
                "detections": [
                    {
                        "class": d.get("class", "unknown"),
                        "confidence": d.get("confidence", 0.0),
                        "severity": d.get("severity", "minor"),
                        "bbox": d.get("bbox", []),
                        "area_pct": d.get("area_pct", 0.0),
                    }
                    for d in detections
                ],
                "annotated_image": data.get("annotated_image", ""),
                "heatmap_image": data.get("heatmap_image", ""),
                "inference_time_ms": data.get("inference_time_ms", 0.0),
            }
            logger.debug(
                f"Inspection {inspection_id}: {'PASS' if not has_defects else f'FAIL ({max_severity.value})'}"
            )
            return result

        except httpx.HTTPError as exc:
            logger.error(f"Inspection failed on pipeline {pipeline_id}: {exc}")
            return {"error": str(exc), "inspection_id": inspection_id, "pipeline_id": pipeline_id}

    async def get_inspection_analytics(self, pipeline_id: str) -> dict:
        """Retrieve aggregated inspection analytics for a pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return {"error": f"Pipeline {pipeline_id} not found"}

        try:
            resp = await self._client.get(f"/metropolis/pipelines/{pipeline_id}/analytics")
            resp.raise_for_status()
            data = resp.json()

            return {
                "pipeline_id": pipeline_id,
                "total_inspections": pipeline.total_inspections,
                "defects_found": pipeline.defects_found,
                "defect_rate_pct": round(
                    (pipeline.defects_found / max(pipeline.total_inspections, 1)) * 100, 2
                ),
                "pass_rate_pct": round(
                    ((pipeline.total_inspections - pipeline.defects_found)
                     / max(pipeline.total_inspections, 1)) * 100, 2
                ),
                "throughput_per_hour": data.get("throughput_per_hour", 0),
                "avg_inference_ms": data.get("avg_inference_ms", 0.0),
                "defect_breakdown": data.get("defect_breakdown", {}),
                "hourly_trend": data.get("hourly_trend", []),
                "false_positive_rate": data.get("false_positive_rate", 0.0),
                "model_confidence_avg": data.get("model_confidence_avg", 0.0),
                "uptime_hours": round((time.time() - pipeline.created_at) / 3600, 1),
            }
        except httpx.HTTPError as exc:
            logger.warning(f"Analytics fetch failed for pipeline {pipeline_id}: {exc}")
            return {
                "pipeline_id": pipeline_id,
                "total_inspections": pipeline.total_inspections,
                "defects_found": pipeline.defects_found,
                "defect_rate_pct": round(
                    (pipeline.defects_found / max(pipeline.total_inspections, 1)) * 100, 2
                ),
                "error": f"Detailed analytics unavailable: {exc}",
            }

    async def retrain_inspector(self, pipeline_id: str,
                                 labeled_images: list[dict]) -> dict:
        """Retrain the inspection model with newly labeled images."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return {"error": f"Pipeline {pipeline_id} not found"}

        retrain_id = f"RTRAIN-{uuid.uuid4().hex[:12].upper()}"

        try:
            resp = await self._client.post(
                f"/metropolis/pipelines/{pipeline_id}/retrain",
                json={
                    "retrain_id": retrain_id,
                    "base_model_id": pipeline.model_id,
                    "labeled_images": [
                        {
                            "image": img.get("image_b64", ""),
                            "annotations": img.get("annotations", []),
                            "quality_label": img.get("quality_label", "pass"),
                        }
                        for img in labeled_images
                    ],
                    "epochs": 50,
                    "learning_rate": 1e-4,
                    "augmentation": True,
                    "validation_split": 0.2,
                    "early_stopping_patience": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            new_model_id = data.get("new_model_id", f"MODEL-{uuid.uuid4().hex[:8].upper()}")
            pipeline.model_id = new_model_id

            result = {
                "retrain_id": retrain_id,
                "pipeline_id": pipeline_id,
                "previous_model_id": pipeline.model_id,
                "new_model_id": new_model_id,
                "images_used": len(labeled_images),
                "epochs_completed": data.get("epochs_completed", 50),
                "training_loss": data.get("training_loss", 0.0),
                "validation_loss": data.get("validation_loss", 0.0),
                "accuracy_improvement_pct": data.get("accuracy_improvement_pct", 0.0),
                "training_time_s": data.get("training_time_s", 0.0),
                "status": "completed",
                "auto_deployed": data.get("auto_deployed", True),
            }
            logger.info(
                f"Inspection model retrained: {retrain_id} — "
                f"{len(labeled_images)} images, "
                f"improvement={result['accuracy_improvement_pct']:.1f}%"
            )
            return result

        except httpx.HTTPError as exc:
            logger.error(f"Retraining failed for pipeline {pipeline_id}: {exc}")
            return {"error": str(exc), "retrain_id": retrain_id, "pipeline_id": pipeline_id}


# ═══════════════════════════════════════════════════════════════════════════════
# Singletons
# ═══════════════════════════════════════════════════════════════════════════════

gpu_cluster = NvidiaGPUCluster()
tensorrt_optimizer = TensorRTOptimizer()
triton_server = TritonServer()
omniverse_connector = OmniverseConnector()
isaac_sim_connector = IsaacSimConnector()
metropolis_connector = MetropolisConnector()
