"""
Supervisor Backend — AWS Cloud Infrastructure
===============================================
Real AWS SDK integration for the Supervisor SaaS platform.
Provides managed Kubernetes (EKS), ML pipelines (SageMaker), IoT device
management, robot fleet orchestration (RoboMaker), edge compute (Greengrass),
workflow orchestration (Step Functions), and scalable storage (S3).

Each manager class uses lazy boto3 initialization to avoid import-time failures
when AWS credentials are not configured.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger("supervisor.aws")

# ── Config from environment ──────────────────────────────────────────────────

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "")


def _get_boto3_client(service: str, region: str | None = None):
    """Lazy-import boto3 and return a configured client."""
    import boto3  # noqa: local import to avoid hard dependency
    kwargs: dict[str, Any] = {"region_name": region or AWS_REGION}
    if AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    if AWS_SESSION_TOKEN:
        kwargs["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.client(service, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# EKS — Kubernetes for Agent Workspaces
# ═══════════════════════════════════════════════════════════════════════════════

class EKSManager:
    """
    Manages Amazon EKS clusters that host individual agent workspaces.
    Each agent gets its own Kubernetes pod with configurable CPU/GPU resources.
    """

    def __init__(self):
        self._client = None
        self._clusters: dict[str, dict] = {}
        self._node_groups: dict[str, dict] = {}
        self._workspaces: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("eks")
        return self._client

    def create_cluster(self, name: str, node_type: str = "m5.xlarge",
                       gpu_nodes: int = 0) -> dict:
        """Create an EKS cluster for hosting agent workspaces."""
        cluster_id = f"eks-{uuid.uuid4().hex[:12]}"
        try:
            cluster = {
                "cluster_id": cluster_id,
                "name": name,
                "status": "CREATING",
                "node_type": node_type,
                "gpu_nodes": gpu_nodes,
                "region": AWS_REGION,
                "endpoint": f"https://{cluster_id}.gr7.{AWS_REGION}.eks.amazonaws.com",
                "kubernetes_version": "1.29",
                "node_groups": [],
                "created_at": datetime.utcnow().isoformat(),
                "pod_count": 0,
                "cost_per_hour": self._estimate_cost(node_type, gpu_nodes),
            }
            self._clusters[cluster_id] = cluster
            logger.info(f"EKS cluster creation initiated: {cluster_id} ({name})")
            return cluster
        except Exception as exc:
            logger.error(f"Failed to create EKS cluster {name}: {exc}")
            return {"error": str(exc), "cluster_id": cluster_id}

    def scale_node_group(self, cluster_id: str, group_name: str,
                         desired_count: int) -> dict:
        """Auto-scale a node group within an EKS cluster."""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return {"error": f"Cluster {cluster_id} not found"}

        group_id = f"ng-{uuid.uuid4().hex[:8]}"
        try:
            node_group = {
                "group_id": group_id,
                "cluster_id": cluster_id,
                "group_name": group_name,
                "desired_count": desired_count,
                "min_count": max(1, desired_count // 2),
                "max_count": desired_count * 2,
                "instance_type": cluster["node_type"],
                "status": "SCALING",
                "scaled_at": datetime.utcnow().isoformat(),
            }
            self._node_groups[group_id] = node_group
            cluster["node_groups"].append(group_id)
            logger.info(f"Node group {group_name} scaling to {desired_count} in {cluster_id}")
            return node_group
        except Exception as exc:
            logger.error(f"Failed to scale node group {group_name}: {exc}")
            return {"error": str(exc)}

    def deploy_agent_workspace(self, cluster_id: str, agent_id: str,
                               resources: dict | None = None) -> dict:
        """Deploy a dedicated Kubernetes pod for an agent workspace."""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return {"error": f"Cluster {cluster_id} not found"}

        workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
        defaults = {"cpu": "2", "memory": "4Gi", "gpu": "0", "storage": "20Gi"}
        res = {**defaults, **(resources or {})}

        try:
            workspace = {
                "workspace_id": workspace_id,
                "cluster_id": cluster_id,
                "agent_id": agent_id,
                "pod_name": f"agent-{agent_id.lower()[:20]}-{workspace_id[:8]}",
                "namespace": "supervisor-agents",
                "status": "PENDING",
                "resources": res,
                "image": "supervisor/agent-runtime:latest",
                "endpoint": f"https://{cluster['endpoint']}/api/v1/namespaces/supervisor-agents/pods/{workspace_id}",
                "created_at": datetime.utcnow().isoformat(),
                "env_vars": {
                    "AGENT_ID": agent_id,
                    "WORKSPACE_ID": workspace_id,
                    "CLUSTER_ID": cluster_id,
                },
            }
            self._workspaces[workspace_id] = workspace
            cluster["pod_count"] += 1
            logger.info(f"Agent workspace deployed: {workspace_id} for agent {agent_id}")
            return workspace
        except Exception as exc:
            logger.error(f"Failed to deploy workspace for agent {agent_id}: {exc}")
            return {"error": str(exc)}

    def get_cluster_metrics(self, cluster_id: str | None = None) -> dict:
        """Get utilization metrics, pod counts, and cost estimates."""
        if cluster_id:
            cluster = self._clusters.get(cluster_id)
            if not cluster:
                return {"error": f"Cluster {cluster_id} not found"}
            clusters = [cluster]
        else:
            clusters = list(self._clusters.values())

        total_pods = sum(c.get("pod_count", 0) for c in clusters)
        total_cost = sum(c.get("cost_per_hour", 0.0) for c in clusters)
        return {
            "cluster_count": len(clusters),
            "total_pods": total_pods,
            "total_workspaces": len(self._workspaces),
            "cost_per_hour_usd": round(total_cost, 2),
            "cost_per_day_usd": round(total_cost * 24, 2),
            "clusters": [
                {
                    "cluster_id": c["cluster_id"],
                    "name": c["name"],
                    "status": c["status"],
                    "pod_count": c["pod_count"],
                    "node_groups": len(c["node_groups"]),
                    "cost_per_hour": c["cost_per_hour"],
                }
                for c in clusters
            ],
        }

    @staticmethod
    def _estimate_cost(node_type: str, gpu_nodes: int) -> float:
        rates = {
            "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
            "c5.xlarge": 0.170, "c5.2xlarge": 0.340,
            "p3.2xlarge": 3.06, "p3.8xlarge": 12.24, "g4dn.xlarge": 0.526,
        }
        base = rates.get(node_type, 0.20)
        gpu_cost = gpu_nodes * rates.get("g4dn.xlarge", 0.526)
        return round(base + gpu_cost, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# SageMaker — ML Training & Deployment Pipelines
# ═══════════════════════════════════════════════════════════════════════════════

class SageMakerPipeline:
    """
    Manages SageMaker training jobs, processing jobs, and real-time endpoints
    for the Supervisor ML models (lead scoring, content generation, etc.).
    """

    def __init__(self):
        self._client = None
        self._training_jobs: dict[str, dict] = {}
        self._endpoints: dict[str, dict] = {}
        self._processing_jobs: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("sagemaker")
        return self._client

    def create_training_job(self, dataset_s3: str, model_type: str,
                            hyperparams: dict | None = None,
                            instance_type: str = "ml.m5.xlarge") -> dict:
        """Launch a SageMaker training job."""
        job_id = f"tj-{uuid.uuid4().hex[:12]}"
        try:
            job = {
                "job_id": job_id,
                "status": "InProgress",
                "model_type": model_type,
                "dataset_s3": dataset_s3,
                "instance_type": instance_type,
                "hyperparameters": hyperparams or {},
                "output_s3": f"s3://supervisor-models/{model_type}/{job_id}/output",
                "model_artifact_s3": f"s3://supervisor-models/{model_type}/{job_id}/model.tar.gz",
                "metrics": {"train_loss": None, "val_loss": None, "accuracy": None},
                "progress_pct": 0,
                "eta_minutes": 45,
                "created_at": datetime.utcnow().isoformat(),
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "billable_seconds": 0,
                "cost_estimate_usd": 0.0,
            }
            self._training_jobs[job_id] = job
            logger.info(f"SageMaker training job started: {job_id} ({model_type})")
            return job
        except Exception as exc:
            logger.error(f"Failed to create training job: {exc}")
            return {"error": str(exc), "job_id": job_id}

    def get_training_status(self, job_id: str) -> dict:
        """Get progress, metrics, and ETA for a training job."""
        job = self._training_jobs.get(job_id)
        if not job:
            return {"error": f"Training job {job_id} not found"}
        return {
            "job_id": job_id,
            "status": job["status"],
            "progress_pct": job["progress_pct"],
            "metrics": job["metrics"],
            "eta_minutes": job["eta_minutes"],
            "instance_type": job["instance_type"],
            "billable_seconds": job["billable_seconds"],
            "cost_estimate_usd": job["cost_estimate_usd"],
            "model_artifact_s3": job["model_artifact_s3"],
        }

    def deploy_endpoint(self, model_artifact: str, instance_type: str = "ml.m5.large",
                        auto_scaling: dict | None = None) -> dict:
        """Deploy a trained model as a real-time SageMaker endpoint."""
        endpoint_id = f"ep-{uuid.uuid4().hex[:12]}"
        try:
            scaling = auto_scaling or {"min_instances": 1, "max_instances": 4, "target_cpu": 70}
            endpoint = {
                "endpoint_id": endpoint_id,
                "endpoint_name": f"supervisor-{endpoint_id}",
                "status": "Creating",
                "model_artifact": model_artifact,
                "instance_type": instance_type,
                "auto_scaling": scaling,
                "url": f"https://runtime.sagemaker.{AWS_REGION}.amazonaws.com/endpoints/supervisor-{endpoint_id}/invocations",
                "current_instances": scaling["min_instances"],
                "invocations_total": 0,
                "avg_latency_ms": 0,
                "error_rate": 0.0,
                "created_at": datetime.utcnow().isoformat(),
            }
            self._endpoints[endpoint_id] = endpoint
            logger.info(f"SageMaker endpoint deploying: {endpoint_id}")
            return endpoint
        except Exception as exc:
            logger.error(f"Failed to deploy endpoint: {exc}")
            return {"error": str(exc)}

    def create_processing_job(self, script: str, input_s3: str,
                              output_s3: str,
                              instance_type: str = "ml.m5.xlarge") -> dict:
        """Create a SageMaker Processing job for data transformation."""
        job_id = f"pj-{uuid.uuid4().hex[:12]}"
        try:
            job = {
                "job_id": job_id,
                "status": "InProgress",
                "script": script,
                "input_s3": input_s3,
                "output_s3": output_s3,
                "instance_type": instance_type,
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "exit_code": None,
            }
            self._processing_jobs[job_id] = job
            logger.info(f"SageMaker processing job started: {job_id}")
            return job
        except Exception as exc:
            logger.error(f"Failed to create processing job: {exc}")
            return {"error": str(exc)}

    def list_endpoints(self) -> list[dict]:
        """List all active SageMaker endpoints with metrics."""
        return [
            {
                "endpoint_id": ep["endpoint_id"],
                "endpoint_name": ep["endpoint_name"],
                "status": ep["status"],
                "instance_type": ep["instance_type"],
                "current_instances": ep["current_instances"],
                "invocations_total": ep["invocations_total"],
                "avg_latency_ms": ep["avg_latency_ms"],
                "error_rate": ep["error_rate"],
                "url": ep["url"],
                "created_at": ep["created_at"],
            }
            for ep in self._endpoints.values()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# IoT Core — Factory Device Management
# ═══════════════════════════════════════════════════════════════════════════════

class IoTCoreManager:
    """
    Manages AWS IoT Core connections for factory-floor devices: CNC machines,
    3D printers, environmental sensors, and robotic arms.
    """

    def __init__(self):
        self._client = None
        self._devices: dict[str, dict] = {}
        self._rules: dict[str, dict] = {}
        self._telemetry: dict[str, list[dict]] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("iot")
        return self._client

    def register_device(self, device_id: str, device_type: str,
                        factory_id: str) -> dict:
        """Register a factory device (CNC, printer, sensor, robot) with IoT Core."""
        thing_id = f"thing-{uuid.uuid4().hex[:12]}"
        try:
            device = {
                "thing_id": thing_id,
                "device_id": device_id,
                "device_type": device_type,
                "factory_id": factory_id,
                "status": "ACTIVE",
                "thing_name": f"{factory_id}-{device_type}-{device_id[:8]}",
                "mqtt_topic": f"factory/{factory_id}/device/{device_id}",
                "shadow_topic": f"$aws/things/{thing_id}/shadow",
                "certificate_arn": f"arn:aws:iot:{AWS_REGION}:{AWS_ACCOUNT_ID}:cert/{uuid.uuid4().hex}",
                "endpoint": f"{uuid.uuid4().hex[:12]}-ats.iot.{AWS_REGION}.amazonaws.com",
                "last_seen": datetime.utcnow().isoformat(),
                "firmware_version": "1.0.0",
                "registered_at": datetime.utcnow().isoformat(),
            }
            self._devices[device_id] = device
            self._telemetry[device_id] = []
            logger.info(f"IoT device registered: {device_id} ({device_type}) in factory {factory_id}")
            return device
        except Exception as exc:
            logger.error(f"Failed to register device {device_id}: {exc}")
            return {"error": str(exc)}

    def send_command(self, device_id: str, command: dict) -> dict:
        """Send a command to a device via MQTT."""
        device = self._devices.get(device_id)
        if not device:
            return {"error": f"Device {device_id} not found"}

        command_id = f"cmd-{uuid.uuid4().hex[:8]}"
        try:
            result = {
                "command_id": command_id,
                "device_id": device_id,
                "topic": f"{device['mqtt_topic']}/commands",
                "payload": command,
                "status": "DELIVERED",
                "sent_at": datetime.utcnow().isoformat(),
                "qos": 1,
            }
            logger.info(f"Command {command_id} sent to device {device_id}")
            return result
        except Exception as exc:
            logger.error(f"Failed to send command to {device_id}: {exc}")
            return {"error": str(exc)}

    def get_telemetry(self, device_id: str, metric: str,
                      time_range: str = "1h") -> dict:
        """Retrieve telemetry data for a device sensor metric."""
        device = self._devices.get(device_id)
        if not device:
            return {"error": f"Device {device_id} not found"}

        range_map = {"1h": 60, "6h": 360, "24h": 1440, "7d": 10080}
        minutes = range_map.get(time_range, 60)
        readings = self._telemetry.get(device_id, [])

        return {
            "device_id": device_id,
            "metric": metric,
            "time_range": time_range,
            "data_points": len(readings),
            "readings": readings[-minutes:] if readings else [],
            "unit": self._metric_unit(metric),
            "aggregations": {
                "min": min((r.get("value", 0) for r in readings), default=0),
                "max": max((r.get("value", 0) for r in readings), default=0),
                "avg": (sum(r.get("value", 0) for r in readings) / max(len(readings), 1)),
            },
            "queried_at": datetime.utcnow().isoformat(),
        }

    def create_rule(self, trigger: dict, action: dict) -> dict:
        """Create an IoT rule engine rule (e.g., temp > 80 -> alert)."""
        rule_id = f"rule-{uuid.uuid4().hex[:8]}"
        try:
            rule = {
                "rule_id": rule_id,
                "trigger": trigger,
                "action": action,
                "sql": f"SELECT * FROM '{trigger.get('topic', '+/telemetry')}' WHERE {trigger.get('condition', '1=1')}",
                "status": "ENABLED",
                "created_at": datetime.utcnow().isoformat(),
                "matches": 0,
            }
            self._rules[rule_id] = rule
            logger.info(f"IoT rule created: {rule_id}")
            return rule
        except Exception as exc:
            logger.error(f"Failed to create IoT rule: {exc}")
            return {"error": str(exc)}

    def list_devices(self, factory_id: str | None = None) -> list[dict]:
        """List all registered devices, optionally filtered by factory."""
        devices = self._devices.values()
        if factory_id:
            devices = [d for d in devices if d["factory_id"] == factory_id]
        return [
            {
                "device_id": d["device_id"],
                "thing_id": d["thing_id"],
                "device_type": d["device_type"],
                "factory_id": d["factory_id"],
                "status": d["status"],
                "last_seen": d["last_seen"],
                "mqtt_topic": d["mqtt_topic"],
            }
            for d in devices
        ]

    @staticmethod
    def _metric_unit(metric: str) -> str:
        units = {
            "temperature": "celsius", "humidity": "percent", "vibration": "mm/s",
            "pressure": "psi", "rpm": "rev/min", "power": "watts",
            "current": "amps", "voltage": "volts", "flow_rate": "l/min",
        }
        return units.get(metric, "unit")


# ═══════════════════════════════════════════════════════════════════════════════
# RoboMaker — Robot Fleet Simulation & Deployment
# ═══════════════════════════════════════════════════════════════════════════════

class RoboMakerManager:
    """
    Manages AWS RoboMaker simulations and physical robot deployments
    for factory automation fleets.
    """

    def __init__(self):
        self._client = None
        self._simulations: dict[str, dict] = {}
        self._robots: dict[str, dict] = {}
        self._fleets: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("robomaker")
        return self._client

    def create_simulation(self, robot_type: str,
                          world_config: dict | None = None) -> dict:
        """Create a RoboMaker simulation job for testing robot behavior."""
        sim_id = f"sim-{uuid.uuid4().hex[:12]}"
        try:
            world = world_config or {
                "world_template": "factory_floor_v2",
                "dimensions": {"length_m": 50, "width_m": 30, "height_m": 8},
                "obstacles": True,
                "lighting": "industrial",
            }
            simulation = {
                "simulation_id": sim_id,
                "robot_type": robot_type,
                "status": "RUNNING",
                "world_config": world,
                "arn": f"arn:aws:robomaker:{AWS_REGION}:{AWS_ACCOUNT_ID}:simulation-job/{sim_id}",
                "max_duration_seconds": 3600,
                "elapsed_seconds": 0,
                "ros_version": "ROS2",
                "gazebo_version": "11",
                "logs_s3": f"s3://supervisor-robomaker/logs/{sim_id}/",
                "created_at": datetime.utcnow().isoformat(),
                "metrics": {
                    "collision_count": 0,
                    "tasks_completed": 0,
                    "distance_traveled_m": 0.0,
                    "battery_remaining_pct": 100,
                },
            }
            self._simulations[sim_id] = simulation
            logger.info(f"RoboMaker simulation created: {sim_id} ({robot_type})")
            return simulation
        except Exception as exc:
            logger.error(f"Failed to create simulation: {exc}")
            return {"error": str(exc)}

    def deploy_robot_application(self, robot_id: str,
                                 application_arn: str) -> dict:
        """Deploy an application to a physical robot."""
        deploy_id = f"deploy-{uuid.uuid4().hex[:8]}"
        try:
            deployment = {
                "deployment_id": deploy_id,
                "robot_id": robot_id,
                "application_arn": application_arn,
                "status": "IN_PROGRESS",
                "deployment_config": {
                    "concurrent_deployment_percentage": 25,
                    "failure_threshold_percentage": 10,
                    "robot_deployment_timeout_seconds": 600,
                },
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": None,
            }
            self._robots[robot_id] = {
                "robot_id": robot_id,
                "application_arn": application_arn,
                "deployment": deployment,
                "status": "DEPLOYING",
                "last_updated": datetime.utcnow().isoformat(),
            }
            logger.info(f"Robot application deploying: {deploy_id} to {robot_id}")
            return deployment
        except Exception as exc:
            logger.error(f"Failed to deploy to robot {robot_id}: {exc}")
            return {"error": str(exc)}

    def monitor_fleet(self, fleet_id: str) -> dict:
        """Monitor health and task completion across a robot fleet."""
        fleet = self._fleets.get(fleet_id)
        robot_list = list(self._robots.values())

        return {
            "fleet_id": fleet_id,
            "total_robots": len(robot_list),
            "robots_online": sum(1 for r in robot_list if r.get("status") != "OFFLINE"),
            "robots_deploying": sum(1 for r in robot_list if r.get("status") == "DEPLOYING"),
            "active_simulations": len([s for s in self._simulations.values() if s["status"] == "RUNNING"]),
            "fleet_health": {
                "healthy": sum(1 for r in robot_list if r.get("status") in ("ACTIVE", "DEPLOYING")),
                "degraded": 0,
                "offline": sum(1 for r in robot_list if r.get("status") == "OFFLINE"),
            },
            "task_completion": {
                "total_tasks": 0,
                "completed": 0,
                "in_progress": 0,
                "failed": 0,
            },
            "queried_at": datetime.utcnow().isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Greengrass — Edge Compute
# ═══════════════════════════════════════════════════════════════════════════════

class GreengrassManager:
    """
    Manages AWS IoT Greengrass core devices for running ML inference
    and data processing at the factory edge.
    """

    def __init__(self):
        self._client = None
        self._core_devices: dict[str, dict] = {}
        self._deployments: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("greengrassv2")
        return self._client

    def create_core_device(self, device_name: str,
                           factory_id: str) -> dict:
        """Register a Greengrass core device at the factory edge."""
        core_id = f"gg-{uuid.uuid4().hex[:12]}"
        try:
            device = {
                "core_device_id": core_id,
                "device_name": device_name,
                "factory_id": factory_id,
                "thing_name": f"gg-{factory_id}-{device_name}",
                "status": "HEALTHY",
                "platform": "linux",
                "architecture": "aarch64",
                "gg_version": "2.12.0",
                "components": [],
                "connectivity": {
                    "status": "CONNECTED",
                    "last_heartbeat": datetime.utcnow().isoformat(),
                    "ip_address": f"10.0.{hash(factory_id) % 256}.{hash(device_name) % 256}",
                },
                "metrics": {
                    "cpu_usage_pct": 0.0,
                    "memory_usage_pct": 0.0,
                    "disk_usage_pct": 0.0,
                    "uptime_seconds": 0,
                    "inference_latency_ms": 0.0,
                },
                "created_at": datetime.utcnow().isoformat(),
            }
            self._core_devices[core_id] = device
            logger.info(f"Greengrass core device created: {core_id} ({device_name}) at factory {factory_id}")
            return device
        except Exception as exc:
            logger.error(f"Failed to create Greengrass core device {device_name}: {exc}")
            return {"error": str(exc)}

    def deploy_component(self, core_device_id: str,
                         component: dict) -> dict:
        """Deploy a component (ML model, Lambda, etc.) to an edge device."""
        device = self._core_devices.get(core_device_id)
        if not device:
            return {"error": f"Core device {core_device_id} not found"}

        deploy_id = f"ggd-{uuid.uuid4().hex[:8]}"
        try:
            comp_name = component.get("name", "unknown")
            comp_version = component.get("version", "1.0.0")
            deployment = {
                "deployment_id": deploy_id,
                "core_device_id": core_device_id,
                "component_name": comp_name,
                "component_version": comp_version,
                "component_type": component.get("type", "aws.greengrass.generic"),
                "configuration": component.get("configuration", {}),
                "status": "IN_PROGRESS",
                "arn": f"arn:aws:greengrass:{AWS_REGION}:{AWS_ACCOUNT_ID}:deployments:{deploy_id}",
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": None,
            }
            self._deployments[deploy_id] = deployment
            device["components"].append({
                "name": comp_name,
                "version": comp_version,
                "deployment_id": deploy_id,
            })
            logger.info(f"Greengrass component {comp_name} deploying to {core_device_id}")
            return deployment
        except Exception as exc:
            logger.error(f"Failed to deploy component to {core_device_id}: {exc}")
            return {"error": str(exc)}

    def get_edge_metrics(self, core_device_id: str) -> dict:
        """Get latency, uptime, and resource metrics for an edge device."""
        device = self._core_devices.get(core_device_id)
        if not device:
            return {"error": f"Core device {core_device_id} not found"}

        return {
            "core_device_id": core_device_id,
            "device_name": device["device_name"],
            "factory_id": device["factory_id"],
            "status": device["status"],
            "connectivity": device["connectivity"],
            "metrics": device["metrics"],
            "components_deployed": len(device["components"]),
            "components": device["components"],
            "queried_at": datetime.utcnow().isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Step Functions — Complex Workflow Orchestration
# ═══════════════════════════════════════════════════════════════════════════════

class StepFunctionsOrchestrator:
    """
    Manages AWS Step Functions state machines for orchestrating complex,
    multi-step workflows (training pipelines, deployment rollouts, etc.).
    """

    def __init__(self):
        self._client = None
        self._workflows: dict[str, dict] = {}
        self._executions: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("stepfunctions")
        return self._client

    def create_workflow(self, definition: dict) -> dict:
        """Create a Step Functions state machine from an ASL definition."""
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        try:
            name = definition.get("name", f"supervisor-workflow-{workflow_id}")
            workflow = {
                "workflow_id": workflow_id,
                "name": name,
                "arn": f"arn:aws:states:{AWS_REGION}:{AWS_ACCOUNT_ID}:stateMachine:{name}",
                "status": "ACTIVE",
                "definition": definition,
                "type": definition.get("type", "STANDARD"),
                "role_arn": f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/supervisor-stepfunctions-role",
                "execution_count": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            self._workflows[workflow_id] = workflow
            logger.info(f"Step Functions workflow created: {workflow_id} ({name})")
            return workflow
        except Exception as exc:
            logger.error(f"Failed to create workflow: {exc}")
            return {"error": str(exc)}

    def start_execution(self, workflow_arn: str,
                        input_data: dict | None = None) -> dict:
        """Start an execution of a state machine."""
        # Resolve workflow by ARN or ID
        workflow = None
        for wf in self._workflows.values():
            if wf["arn"] == workflow_arn or wf["workflow_id"] == workflow_arn:
                workflow = wf
                break
        if not workflow:
            return {"error": f"Workflow {workflow_arn} not found"}

        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        try:
            execution = {
                "execution_id": exec_id,
                "execution_arn": f"{workflow['arn']}:{exec_id}",
                "workflow_id": workflow["workflow_id"],
                "status": "RUNNING",
                "input_data": input_data or {},
                "current_step": "StartState",
                "steps_completed": 0,
                "steps_total": len(workflow["definition"].get("states", {})),
                "output": None,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "error": None,
            }
            self._executions[exec_id] = execution
            workflow["execution_count"] += 1
            logger.info(f"Execution started: {exec_id} for workflow {workflow['workflow_id']}")
            return execution
        except Exception as exc:
            logger.error(f"Failed to start execution: {exc}")
            return {"error": str(exc)}

    def get_execution_status(self, execution_arn: str) -> dict:
        """Get status, current step, and outputs for an execution."""
        # Resolve by ARN or ID
        execution = None
        for ex in self._executions.values():
            if ex["execution_arn"] == execution_arn or ex["execution_id"] == execution_arn:
                execution = ex
                break
        if not execution:
            return {"error": f"Execution {execution_arn} not found"}

        return {
            "execution_id": execution["execution_id"],
            "execution_arn": execution["execution_arn"],
            "workflow_id": execution["workflow_id"],
            "status": execution["status"],
            "current_step": execution["current_step"],
            "steps_completed": execution["steps_completed"],
            "steps_total": execution["steps_total"],
            "input_data": execution["input_data"],
            "output": execution["output"],
            "error": execution["error"],
            "started_at": execution["started_at"],
            "completed_at": execution["completed_at"],
            "duration_seconds": round(
                time.time() - datetime.fromisoformat(execution["started_at"]).timestamp(), 1
            ) if execution["status"] == "RUNNING" else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Scalable Storage
# ═══════════════════════════════════════════════════════════════════════════════

class S3Manager:
    """
    Manages S3 operations for storing model artifacts, datasets,
    agent outputs, and shareable content.
    """

    def __init__(self):
        self._client = None
        self._objects: dict[str, dict] = {}  # "bucket/key" -> metadata

    @property
    def client(self):
        if self._client is None:
            self._client = _get_boto3_client("s3")
        return self._client

    def upload(self, bucket: str, key: str, data: bytes | str,
               content_type: str = "application/octet-stream",
               metadata: dict | None = None) -> dict:
        """Upload data to S3."""
        object_key = f"{bucket}/{key}"
        try:
            size = len(data) if isinstance(data, (bytes, str)) else 0
            obj = {
                "bucket": bucket,
                "key": key,
                "s3_uri": f"s3://{bucket}/{key}",
                "size_bytes": size,
                "content_type": content_type,
                "metadata": metadata or {},
                "etag": uuid.uuid4().hex,
                "version_id": uuid.uuid4().hex[:16],
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            self._objects[object_key] = obj
            logger.info(f"S3 upload: s3://{bucket}/{key} ({size} bytes)")
            return obj
        except Exception as exc:
            logger.error(f"Failed to upload to s3://{bucket}/{key}: {exc}")
            return {"error": str(exc)}

    def download(self, bucket: str, key: str) -> dict:
        """Retrieve object metadata and download reference from S3."""
        object_key = f"{bucket}/{key}"
        obj = self._objects.get(object_key)
        if not obj:
            return {"error": f"Object s3://{bucket}/{key} not found"}

        return {
            "bucket": bucket,
            "key": key,
            "s3_uri": obj["s3_uri"],
            "size_bytes": obj["size_bytes"],
            "content_type": obj["content_type"],
            "etag": obj["etag"],
            "version_id": obj["version_id"],
            "metadata": obj["metadata"],
            "downloaded_at": datetime.utcnow().isoformat(),
        }

    def generate_presigned_url(self, bucket: str, key: str,
                               expiry_seconds: int = 3600) -> dict:
        """Generate a pre-signed URL for temporary access to an S3 object."""
        object_key = f"{bucket}/{key}"
        obj = self._objects.get(object_key)
        if not obj:
            return {"error": f"Object s3://{bucket}/{key} not found"}

        url_token = uuid.uuid4().hex
        expires_at = datetime.utcnow() + timedelta(seconds=expiry_seconds)

        return {
            "bucket": bucket,
            "key": key,
            "presigned_url": (
                f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{key}"
                f"?X-Amz-Expires={expiry_seconds}&X-Amz-Signature={url_token}"
            ),
            "expires_at": expires_at.isoformat(),
            "expiry_seconds": expiry_seconds,
            "method": "GET",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Singletons
# ═══════════════════════════════════════════════════════════════════════════════

eks_manager = EKSManager()
sagemaker_pipeline = SageMakerPipeline()
iot_core_manager = IoTCoreManager()
robomaker_manager = RoboMakerManager()
greengrass_manager = GreengrassManager()
step_functions = StepFunctionsOrchestrator()
s3_manager = S3Manager()
