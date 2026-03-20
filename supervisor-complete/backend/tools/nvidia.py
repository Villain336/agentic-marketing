"""
GPU allocation, TensorRT, Triton inference, digital twins, robotics, and vision inspection.
"""

from __future__ import annotations

import json

from tools.registry import _to_json


async def _allocate_gpu(agent_id: str, gpu_type: str = "", vram_gb: str = "0") -> str:
    try:
        from nvidia_infra import gpu_cluster
        result = await gpu_cluster.allocate_gpu(agent_id, gpu_type, float(vram_gb))
        if result:
            return _to_json(result)
        return json.dumps({"error": "No GPU available matching requirements", "agent_id": agent_id})
    except Exception as e:
        return json.dumps({"error": str(e), "agent_id": agent_id, "note": "NVIDIA GPU cluster not available"})



async def _release_gpu(allocation_id: str) -> str:
    try:
        from nvidia_infra import gpu_cluster
        ok = await gpu_cluster.release_gpu(allocation_id)
        return json.dumps({"released": ok, "allocation_id": allocation_id})
    except Exception as e:
        return json.dumps({"error": str(e), "allocation_id": allocation_id})



async def _gpu_cluster_status() -> str:
    try:
        from nvidia_infra import gpu_cluster
        result = await gpu_cluster.get_cluster_status()
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "note": "NVIDIA GPU cluster not available"})



async def _optimize_model_tensorrt(model_path: str, precision: str = "fp16",
                                     target_gpu: str = "", model_name: str = "") -> str:
    try:
        from nvidia_infra import tensorrt_optimizer
        engine = await tensorrt_optimizer.optimize_model(model_path, precision, target_gpu, model_name)
        return _to_json(engine)
    except Exception as e:
        return json.dumps({"error": str(e), "model_path": model_path})



async def _deploy_model_triton(model_name: str, model_path: str,
                                 instances: str = "1", gpu_ids: str = "") -> str:
    try:
        from nvidia_infra import triton_server
        gids = [g.strip() for g in gpu_ids.split(",") if g.strip()] if gpu_ids else []
        model = await triton_server.deploy_model(model_name, model_path, int(instances), gids)
        return _to_json(model)
    except Exception as e:
        return json.dumps({"error": str(e), "model_name": model_name})



async def _triton_infer(model_name: str, inputs: str = "{}") -> str:
    try:
        from nvidia_infra import triton_server
        inp = json.loads(inputs) if isinstance(inputs, str) else inputs
        result = await triton_server.infer(model_name, inp)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "model_name": model_name})



async def _create_digital_twin(name: str = "", factory_config: str = "{}") -> str:
    try:
        from nvidia_infra import omniverse_connector
        config = json.loads(factory_config) if isinstance(factory_config, str) else factory_config
        twin = await omniverse_connector.create_digital_twin(config, name)
        return _to_json(twin)
    except Exception as e:
        return json.dumps({"error": str(e), "name": name})



async def _simulate_digital_twin(twin_id: str, scenario: str = "{}") -> str:
    try:
        from nvidia_infra import omniverse_connector
        sc = json.loads(scenario) if isinstance(scenario, str) else scenario
        result = await omniverse_connector.simulate(twin_id, sc)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "twin_id": twin_id})



async def _create_robot_sim(robot_type: str, task: str) -> str:
    try:
        from nvidia_infra import isaac_sim_connector
        sim = await isaac_sim_connector.create_robot_sim(robot_type, task)
        return _to_json(sim)
    except Exception as e:
        return json.dumps({"error": str(e), "robot_type": robot_type})



async def _train_robot_policy(sim_id: str, algorithm: str = "PPO", episodes: str = "1000") -> str:
    try:
        from nvidia_infra import isaac_sim_connector
        result = await isaac_sim_connector.train_robot_policy(sim_id, algorithm, int(episodes))
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "sim_id": sim_id})



async def _run_vision_inspection(pipeline_id: str, image_b64: str = "") -> str:
    try:
        from nvidia_infra import metropolis_connector
        result = await metropolis_connector.run_inspection(pipeline_id, image_b64)
        return _to_json(result)
    except Exception as e:
        return json.dumps({"error": str(e), "pipeline_id": pipeline_id})



def register_nvidia_tools(registry):
    """Register all nvidia tools with the given registry."""
    from models import ToolParameter

    registry.register("allocate_gpu", "Reserve a GPU for an agent task — supports A100, H100, L40S.",
        [ToolParameter(name="agent_id", description="Agent requesting the GPU"),
         ToolParameter(name="gpu_type", description="GPU type: A100, H100, L40S", required=False),
         ToolParameter(name="vram_gb", description="Minimum VRAM in GB", required=False)],
        _allocate_gpu, "nvidia")

    registry.register("release_gpu", "Release a previously allocated GPU back to the pool.",
        [ToolParameter(name="allocation_id", description="Allocation ID to release")],
        _release_gpu, "nvidia")

    registry.register("gpu_cluster_status", "Get GPU cluster status — total GPUs, utilization, queue depth.",
        [], _gpu_cluster_status, "nvidia")

    registry.register("optimize_model_tensorrt", "Optimize a model for inference with TensorRT — FP16/INT8/FP32.",
        [ToolParameter(name="model_path", description="Path to ONNX/PyTorch model"),
         ToolParameter(name="precision", description="Precision: fp16, int8, fp32", required=False),
         ToolParameter(name="target_gpu", description="Target GPU type", required=False),
         ToolParameter(name="model_name", description="Name for the optimized model", required=False)],
        _optimize_model_tensorrt, "nvidia")

    registry.register("deploy_model_triton", "Deploy a model on NVIDIA Triton Inference Server.",
        [ToolParameter(name="model_name", description="Model name"),
         ToolParameter(name="model_path", description="Path to model files"),
         ToolParameter(name="instances", description="Number of instances", required=False),
         ToolParameter(name="gpu_ids", description="Comma-separated GPU IDs", required=False)],
        _deploy_model_triton, "nvidia")

    registry.register("triton_infer", "Run inference against a Triton-deployed model.",
        [ToolParameter(name="model_name", description="Deployed model name"),
         ToolParameter(name="inputs", description="Input data as JSON", required=False)],
        _triton_infer, "nvidia")

    registry.register("create_digital_twin", "Create an NVIDIA Omniverse digital twin of a factory.",
        [ToolParameter(name="name", description="Twin name", required=False),
         ToolParameter(name="factory_config", description="Factory config JSON", required=False)],
        _create_digital_twin, "nvidia")

    registry.register("simulate_digital_twin", "Run simulation on a digital twin — throughput, bottlenecks, failures.",
        [ToolParameter(name="twin_id", description="Digital twin ID"),
         ToolParameter(name="scenario", description="Scenario config JSON", required=False)],
        _simulate_digital_twin, "nvidia")

    registry.register("create_robot_sim", "Create a robotics simulation in NVIDIA Isaac Sim.",
        [ToolParameter(name="robot_type", description="Robot type (e.g. industrial_arm, mobile_robot)"),
         ToolParameter(name="task", description="Task to simulate (e.g. pick_and_place, welding)")],
        _create_robot_sim, "nvidia")

    registry.register("train_robot_policy", "Train a robot policy using reinforcement learning in Isaac Sim.",
        [ToolParameter(name="sim_id", description="Simulation ID"),
         ToolParameter(name="algorithm", description="RL algorithm: PPO, SAC, TD3", required=False),
         ToolParameter(name="episodes", description="Training episodes", required=False)],
        _train_robot_policy, "nvidia")

    registry.register("run_vision_inspection", "Run NVIDIA Metropolis vision AI quality inspection on a part.",
        [ToolParameter(name="pipeline_id", description="Inspection pipeline ID"),
         ToolParameter(name="image_b64", description="Base64 encoded image", required=False)],
        _run_vision_inspection, "nvidia")

    # ── AWS Tools ──

