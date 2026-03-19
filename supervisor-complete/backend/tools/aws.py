"""
EKS, SageMaker, IoT Core, RoboMaker, Greengrass, Step Functions, and S3.
"""

from __future__ import annotations

import json

from tools.registry import _to_json


async def _eks_create_cluster(name: str, node_type: str = "m5.xlarge", gpu_nodes: str = "0") -> str:
    try:
        from aws_infra import eks_manager
        result = await eks_manager.create_cluster(name, node_type, int(gpu_nodes))
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "name": name, "note": "AWS EKS not configured"})



async def _eks_deploy_workspace(cluster: str, agent_id: str, cpu: str = "2", memory: str = "4Gi") -> str:
    try:
        from aws_infra import eks_manager
        result = await eks_manager.deploy_agent_workspace(cluster, agent_id, {"cpu": cpu, "memory": memory})
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster": cluster, "agent_id": agent_id})



async def _sagemaker_train(dataset_s3: str, model_type: str, instance_type: str = "ml.g5.xlarge",
                            hyperparams: str = "{}") -> str:
    try:
        from aws_infra import sagemaker_pipeline
        hp = json.loads(hyperparams) if isinstance(hyperparams, str) else hyperparams
        result = await sagemaker_pipeline.create_training_job(dataset_s3, model_type, hp, instance_type)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "dataset_s3": dataset_s3})



async def _sagemaker_deploy_endpoint(model_artifact: str, instance_type: str = "ml.g5.xlarge",
                                       auto_scaling: str = "true") -> str:
    try:
        from aws_infra import sagemaker_pipeline
        result = await sagemaker_pipeline.deploy_endpoint(model_artifact, instance_type, auto_scaling.lower() == "true")
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "model_artifact": model_artifact})



async def _iot_register_device(device_id: str, device_type: str, factory_id: str = "") -> str:
    try:
        from aws_infra import iot_core_manager
        result = await iot_core_manager.register_device(device_id, device_type, factory_id)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "device_id": device_id, "note": "AWS IoT Core not configured"})



async def _iot_send_command(device_id: str, command: str = "{}") -> str:
    try:
        from aws_infra import iot_core_manager
        cmd = json.loads(command) if isinstance(command, str) else command
        result = await iot_core_manager.send_command(device_id, cmd)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "device_id": device_id})



async def _iot_get_telemetry(device_id: str, metric: str = "", time_range: str = "1h") -> str:
    try:
        from aws_infra import iot_core_manager
        result = await iot_core_manager.get_telemetry(device_id, metric, time_range)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "device_id": device_id})



async def _iot_create_rule(trigger: str = "{}", action: str = "{}") -> str:
    try:
        from aws_infra import iot_core_manager
        t = json.loads(trigger) if isinstance(trigger, str) else trigger
        a = json.loads(action) if isinstance(action, str) else action
        result = await iot_core_manager.create_rule(t, a)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e)})



async def _robomaker_create_sim(robot_type: str, world_config: str = "{}") -> str:
    try:
        from aws_infra import robomaker_manager
        wc = json.loads(world_config) if isinstance(world_config, str) else world_config
        result = await robomaker_manager.create_simulation(robot_type, wc)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "robot_type": robot_type})



async def _robomaker_deploy_robot(robot_id: str, application_arn: str) -> str:
    try:
        from aws_infra import robomaker_manager
        result = await robomaker_manager.deploy_robot_application(robot_id, application_arn)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "robot_id": robot_id})



async def _greengrass_deploy_edge(core_device: str, component_name: str, component_type: str = "ml_model") -> str:
    try:
        from aws_infra import greengrass_manager
        result = await greengrass_manager.deploy_component(core_device, {"name": component_name, "type": component_type})
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "core_device": core_device})



async def _step_functions_create_workflow(name: str = "", definition: str = "{}") -> str:
    try:
        from aws_infra import step_functions
        defn = json.loads(definition) if isinstance(definition, str) else definition
        result = await step_functions.create_workflow(defn, name)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "name": name})



async def _step_functions_start(workflow_id: str, input_data: str = "{}") -> str:
    try:
        from aws_infra import step_functions
        inp = json.loads(input_data) if isinstance(input_data, str) else input_data
        result = await step_functions.start_execution(workflow_id, inp)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "workflow_id": workflow_id})



async def _s3_upload(key: str, data: str = "", bucket: str = "") -> str:
    try:
        from aws_infra import s3_manager
        result = await s3_manager.upload(key, data.encode(), bucket)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "key": key, "note": "AWS S3 not configured"})



async def _s3_download(key: str, bucket: str = "") -> str:
    try:
        from aws_infra import s3_manager
        result = await s3_manager.download(key, bucket)
        if isinstance(result.get("data"), bytes):
            result["data"] = f"<binary {result.get('size_bytes', 0)} bytes>"
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "key": key})



def register_aws_tools(registry):
    """Register all aws tools with the given registry."""
    from models import ToolParameter

    registry.register("eks_create_cluster", "Create an EKS Kubernetes cluster for agent workloads.",
        [ToolParameter(name="name", description="Cluster name"),
         ToolParameter(name="node_type", description="Node instance type", required=False),
         ToolParameter(name="gpu_nodes", description="Number of GPU nodes", required=False)],
        _eks_create_cluster, "aws")

    registry.register("eks_deploy_workspace", "Deploy an agent workspace as a Kubernetes pod on EKS.",
        [ToolParameter(name="cluster", description="Cluster name"),
         ToolParameter(name="agent_id", description="Agent ID"),
         ToolParameter(name="cpu", description="CPU allocation", required=False),
         ToolParameter(name="memory", description="Memory allocation", required=False)],
        _eks_deploy_workspace, "aws")

    registry.register("sagemaker_train", "Launch a SageMaker training job.",
        [ToolParameter(name="dataset_s3", description="S3 path to training dataset"),
         ToolParameter(name="model_type", description="Model type to train"),
         ToolParameter(name="instance_type", description="SageMaker instance type", required=False),
         ToolParameter(name="hyperparams", description="Hyperparameters JSON", required=False)],
        _sagemaker_train, "aws")

    registry.register("sagemaker_deploy_endpoint", "Deploy a trained model as a SageMaker real-time endpoint.",
        [ToolParameter(name="model_artifact", description="S3 path to model artifact"),
         ToolParameter(name="instance_type", description="Instance type for endpoint", required=False),
         ToolParameter(name="auto_scaling", description="Enable auto-scaling", required=False)],
        _sagemaker_deploy_endpoint, "aws")

    registry.register("iot_register_device", "Register a factory floor device with AWS IoT Core.",
        [ToolParameter(name="device_id", description="Unique device identifier"),
         ToolParameter(name="device_type", description="Device type: cnc, printer, sensor, robot, conveyor"),
         ToolParameter(name="factory_id", description="Factory identifier", required=False)],
        _iot_register_device, "aws")

    registry.register("iot_send_command", "Send a command to a factory floor device via IoT Core.",
        [ToolParameter(name="device_id", description="Target device ID"),
         ToolParameter(name="command", description="Command JSON", required=False)],
        _iot_send_command, "aws")

    registry.register("iot_get_telemetry", "Read sensor telemetry from a factory device.",
        [ToolParameter(name="device_id", description="Device ID"),
         ToolParameter(name="metric", description="Specific metric: temperature, vibration, power", required=False),
         ToolParameter(name="time_range", description="Time range: 1h, 24h, 7d", required=False)],
        _iot_get_telemetry, "aws")

    registry.register("iot_create_rule", "Create an IoT rule: if condition → trigger action.",
        [ToolParameter(name="trigger", description="Trigger condition JSON"),
         ToolParameter(name="action", description="Action to execute JSON")],
        _iot_create_rule, "aws")

    registry.register("robomaker_create_sim", "Create a robot simulation in AWS RoboMaker.",
        [ToolParameter(name="robot_type", description="Robot type"),
         ToolParameter(name="world_config", description="World configuration JSON", required=False)],
        _robomaker_create_sim, "aws")

    registry.register("robomaker_deploy_robot", "Deploy software to a physical robot via RoboMaker.",
        [ToolParameter(name="robot_id", description="Robot identifier"),
         ToolParameter(name="application_arn", description="Application ARN to deploy")],
        _robomaker_deploy_robot, "aws")

    registry.register("greengrass_deploy_edge", "Deploy ML model or component to edge device via Greengrass.",
        [ToolParameter(name="core_device", description="Greengrass core device name"),
         ToolParameter(name="component_name", description="Component to deploy"),
         ToolParameter(name="component_type", description="Type: ml_model, lambda, container", required=False)],
        _greengrass_deploy_edge, "aws")

    registry.register("step_functions_create_workflow", "Create a Step Functions workflow for multi-agent orchestration.",
        [ToolParameter(name="name", description="Workflow name", required=False),
         ToolParameter(name="definition", description="State machine definition JSON", required=False)],
        _step_functions_create_workflow, "aws")

    registry.register("step_functions_start", "Start execution of a Step Functions workflow.",
        [ToolParameter(name="workflow_id", description="Workflow ID"),
         ToolParameter(name="input_data", description="Input data JSON", required=False)],
        _step_functions_start, "aws")

    registry.register("s3_upload", "Upload an artifact to S3 (CAD files, G-code, models, reports).",
        [ToolParameter(name="key", description="S3 object key/path"),
         ToolParameter(name="data", description="Data to upload", required=False),
         ToolParameter(name="bucket", description="S3 bucket name", required=False)],
        _s3_upload, "aws")

    registry.register("s3_download", "Download an artifact from S3.",
        [ToolParameter(name="key", description="S3 object key/path"),
         ToolParameter(name="bucket", description="S3 bucket name", required=False)],
        _s3_download, "aws")

    # ── Reindustrialization Tools ──

