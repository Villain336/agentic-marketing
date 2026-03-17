"""
Supervisor Backend — SkillForge: Self-Writing Skills System
Agents can create, validate, and register new tools at runtime.
Competes with OpenClaw's self-evolving agent skills.
"""
from __future__ import annotations
import json
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.skillforge")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SkillDefinition(BaseModel):
    """A skill that an agent has authored."""
    id: str = Field(default_factory=lambda: f"skill_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    name: str
    description: str
    parameters: list[dict] = []              # [{name, type, description, required}]
    implementation_type: str = "api_chain"    # api_chain | prompt_template | composite
    implementation: dict = {}                 # Type-specific execution config
    category: str = "custom"
    author_agent_id: str = ""
    author_campaign_id: str = ""
    version: int = 1
    is_validated: bool = False
    is_published: bool = False               # Published to marketplace
    validation_score: float = 0.0            # 0-1 quality score
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = []


class SkillExecutionResult(BaseModel):
    """Result of executing a self-authored skill."""
    skill_id: str
    success: bool
    output: Any = None
    error: str = ""
    execution_time_ms: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# IMPLEMENTATION TYPES
# ═══════════════════════════════════════════════════════════════════════════════

# Skills can be authored in three ways:

# 1. api_chain: Sequence of existing tool calls
#    implementation: {"steps": [{"tool": "web_search", "inputs": {"query": "{{input}}"}}, ...]}

# 2. prompt_template: LLM prompt with variable substitution
#    implementation: {"prompt": "Analyze {{data}} and...", "output_format": "json"}

# 3. composite: Mix of tool calls + LLM reasoning
#    implementation: {"steps": [{"type": "tool", ...}, {"type": "llm", "prompt": "..."}]}


class SkillForge:
    """
    Runtime skill authoring engine.
    Agents request new skills → SkillForge generates, validates, and registers them.
    """

    # Safety: skills cannot call these tools
    BLOCKED_TOOLS = {
        "register_domain", "send_for_signature", "make_phone_call",
    }

    # Max skills per campaign to prevent runaway creation
    MAX_SKILLS_PER_CAMPAIGN = 50

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}     # skill_id -> skill
        self._campaign_skills: dict[str, list[str]] = {}   # campaign_id -> [skill_ids]
        self._global_skills: list[str] = []                # Published skills available to all

    def create_skill(self, name: str, description: str, parameters: list[dict],
                     implementation_type: str, implementation: dict,
                     author_agent_id: str = "", campaign_id: str = "",
                     tags: list[str] = None, category: str = "custom") -> SkillDefinition:
        """
        Create a new skill definition.
        Does NOT auto-register — must be validated first.
        """
        # Enforce limits
        campaign_skills = self._campaign_skills.get(campaign_id, [])
        if len(campaign_skills) >= self.MAX_SKILLS_PER_CAMPAIGN:
            raise ValueError(f"Campaign {campaign_id} has reached max skills ({self.MAX_SKILLS_PER_CAMPAIGN})")

        # Validate implementation type
        if implementation_type not in ("api_chain", "prompt_template", "composite"):
            raise ValueError(f"Invalid implementation type: {implementation_type}")

        # Security: check for blocked tools in api_chain
        if implementation_type in ("api_chain", "composite"):
            steps = implementation.get("steps", [])
            for step in steps:
                tool_name = step.get("tool", "")
                if tool_name in self.BLOCKED_TOOLS:
                    raise ValueError(f"Skill cannot use blocked tool: {tool_name}")

        skill = SkillDefinition(
            name=name, description=description, parameters=parameters,
            implementation_type=implementation_type, implementation=implementation,
            author_agent_id=author_agent_id, author_campaign_id=campaign_id,
            category=category, tags=tags or [],
        )

        self._skills[skill.id] = skill
        if campaign_id:
            if campaign_id not in self._campaign_skills:
                self._campaign_skills[campaign_id] = []
            self._campaign_skills[campaign_id].append(skill.id)

        logger.info(f"Skill created: {skill.name} ({skill.id}) by {author_agent_id}")
        return skill

    def validate_skill(self, skill_id: str, test_inputs: dict = None) -> dict:
        """
        Validate a skill's definition for correctness and safety.
        Returns validation result with score.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return {"valid": False, "error": "Skill not found", "score": 0}

        issues = []
        score = 1.0

        # Check name
        if not skill.name or len(skill.name) < 3:
            issues.append("Name too short (min 3 chars)")
            score -= 0.2

        # Check description
        if not skill.description or len(skill.description) < 10:
            issues.append("Description too short (min 10 chars)")
            score -= 0.1

        # Check implementation
        impl = skill.implementation
        if skill.implementation_type == "api_chain":
            steps = impl.get("steps", [])
            if not steps:
                issues.append("API chain has no steps")
                score -= 0.5
            for i, step in enumerate(steps):
                if "tool" not in step:
                    issues.append(f"Step {i} missing 'tool' field")
                    score -= 0.2

        elif skill.implementation_type == "prompt_template":
            if "prompt" not in impl:
                issues.append("Prompt template missing 'prompt' field")
                score -= 0.5

        elif skill.implementation_type == "composite":
            steps = impl.get("steps", [])
            if not steps:
                issues.append("Composite skill has no steps")
                score -= 0.5
            for i, step in enumerate(steps):
                if "type" not in step:
                    issues.append(f"Step {i} missing 'type' field")
                    score -= 0.1

        # Check for circular references (skill calling itself)
        if skill.implementation_type in ("api_chain", "composite"):
            for step in impl.get("steps", []):
                if step.get("tool") == skill.name:
                    issues.append("Skill cannot call itself (circular reference)")
                    score -= 0.5

        score = max(score, 0.0)
        skill.validation_score = score
        skill.is_validated = score >= 0.6

        result = {
            "valid": skill.is_validated,
            "score": score,
            "issues": issues,
            "skill_id": skill_id,
        }

        logger.info(f"Skill {skill_id} validation: score={score:.2f}, valid={skill.is_validated}")
        return result

    async def execute_skill(self, skill_id: str, inputs: dict,
                            tool_registry=None, llm_router=None) -> SkillExecutionResult:
        """Execute a validated skill."""
        import time
        start = time.time()

        skill = self._skills.get(skill_id)
        if not skill:
            return SkillExecutionResult(skill_id=skill_id, success=False, error="Skill not found")

        if not skill.is_validated:
            return SkillExecutionResult(skill_id=skill_id, success=False, error="Skill not validated")

        try:
            if skill.implementation_type == "api_chain":
                output = await self._execute_api_chain(skill, inputs, tool_registry)
            elif skill.implementation_type == "prompt_template":
                output = await self._execute_prompt_template(skill, inputs, llm_router)
            elif skill.implementation_type == "composite":
                output = await self._execute_composite(skill, inputs, tool_registry, llm_router)
            else:
                return SkillExecutionResult(skill_id=skill_id, success=False,
                                            error=f"Unknown type: {skill.implementation_type}")

            elapsed = int((time.time() - start) * 1000)
            skill.usage_count += 1
            # Update rolling success rate
            skill.success_rate = ((skill.success_rate * (skill.usage_count - 1)) + 1.0) / skill.usage_count

            return SkillExecutionResult(skill_id=skill_id, success=True,
                                        output=output, execution_time_ms=elapsed)

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            skill.usage_count += 1
            skill.success_rate = ((skill.success_rate * (skill.usage_count - 1)) + 0.0) / skill.usage_count
            logger.error(f"Skill {skill_id} execution failed: {e}")
            return SkillExecutionResult(skill_id=skill_id, success=False,
                                        error=str(e), execution_time_ms=elapsed)

    async def _execute_api_chain(self, skill: SkillDefinition, inputs: dict,
                                  tool_registry) -> Any:
        """Execute a chain of tool calls."""
        if not tool_registry:
            raise ValueError("Tool registry required for api_chain skills")

        results = []
        context = {**inputs}  # Mutable context passed between steps

        for step in skill.implementation.get("steps", []):
            tool_name = step["tool"]
            # Resolve template variables in inputs
            step_inputs = {}
            for k, v in step.get("inputs", {}).items():
                if isinstance(v, str) and "{{" in v:
                    for ctx_key, ctx_val in context.items():
                        v = v.replace(f"{{{{{ctx_key}}}}}", str(ctx_val))
                step_inputs[k] = v

            result = await tool_registry.execute(tool_name, step_inputs)
            if not result.success:
                raise RuntimeError(f"Step {tool_name} failed: {result.error}")

            results.append({"tool": tool_name, "output": result.output})
            # Feed output into context for next step
            context[f"step_{len(results)}_output"] = result.output

        return results[-1]["output"] if results else None

    async def _execute_prompt_template(self, skill: SkillDefinition, inputs: dict,
                                        llm_router) -> Any:
        """Execute a prompt template via LLM."""
        if not llm_router:
            raise ValueError("LLM router required for prompt_template skills")

        prompt = skill.implementation["prompt"]
        for k, v in inputs.items():
            prompt = prompt.replace(f"{{{{{k}}}}}", str(v))

        result = await llm_router.complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are a helpful assistant executing a custom skill. Be precise and concise.",
            max_tokens=2048,
        )
        return result.get("text", "")

    async def _execute_composite(self, skill: SkillDefinition, inputs: dict,
                                  tool_registry, llm_router) -> Any:
        """Execute a mix of tool calls and LLM steps."""
        context = {**inputs}
        last_output = None

        for step in skill.implementation.get("steps", []):
            step_type = step.get("type", "tool")

            if step_type == "tool":
                step_inputs = {}
                for k, v in step.get("inputs", {}).items():
                    if isinstance(v, str) and "{{" in v:
                        for ctx_key, ctx_val in context.items():
                            v = v.replace(f"{{{{{ctx_key}}}}}", str(ctx_val))
                    step_inputs[k] = v

                result = await tool_registry.execute(step["tool"], step_inputs)
                if not result.success:
                    raise RuntimeError(f"Tool {step['tool']} failed: {result.error}")
                last_output = result.output
                context[f"tool_output"] = result.output

            elif step_type == "llm":
                prompt = step.get("prompt", "")
                for k, v in context.items():
                    prompt = prompt.replace(f"{{{{{k}}}}}", str(v))
                result = await llm_router.complete(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                )
                last_output = result.get("text", "")
                context["llm_output"] = last_output

        return last_output

    def register_to_tool_registry(self, skill_id: str, tool_registry) -> bool:
        """Register a validated skill as a callable tool in the tool registry."""
        skill = self._skills.get(skill_id)
        if not skill or not skill.is_validated:
            return False

        from models import ToolParameter

        params = []
        for p in skill.parameters:
            params.append(ToolParameter(
                name=p.get("name", "input"),
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
            ))

        async def _handler(inputs: dict) -> str:
            result = await self.execute_skill(skill_id, inputs, tool_registry)
            if result.success:
                return str(result.output) if result.output else "OK"
            return f"Error: {result.error}"

        tool_registry.register(
            name=f"custom_{skill.name}",
            description=f"[Custom Skill] {skill.description}",
            parameters=params,
            handler=_handler,
            category="custom",
        )

        logger.info(f"Skill {skill.name} registered as tool custom_{skill.name}")
        return True

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def list_skills(self, campaign_id: str = None, published_only: bool = False) -> list[SkillDefinition]:
        if campaign_id:
            skill_ids = self._campaign_skills.get(campaign_id, [])
            skills = [self._skills[sid] for sid in skill_ids if sid in self._skills]
        else:
            skills = list(self._skills.values())

        if published_only:
            skills = [s for s in skills if s.is_published]

        return sorted(skills, key=lambda s: s.usage_count, reverse=True)

    def publish_skill(self, skill_id: str) -> bool:
        """Publish a validated skill to the global marketplace."""
        skill = self._skills.get(skill_id)
        if not skill or not skill.is_validated:
            return False
        skill.is_published = True
        if skill_id not in self._global_skills:
            self._global_skills.append(skill_id)
        logger.info(f"Skill {skill.name} published to marketplace")
        return True

    def get_marketplace_skills(self) -> list[SkillDefinition]:
        """Get all published skills available on the marketplace."""
        return [
            self._skills[sid] for sid in self._global_skills
            if sid in self._skills and self._skills[sid].is_published
        ]

    def fork_skill(self, skill_id: str, campaign_id: str) -> Optional[SkillDefinition]:
        """Fork a marketplace skill into a campaign's private skills."""
        source = self._skills.get(skill_id)
        if not source:
            return None

        forked = self.create_skill(
            name=f"{source.name}_fork",
            description=source.description,
            parameters=source.parameters,
            implementation_type=source.implementation_type,
            implementation=source.implementation.copy(),
            campaign_id=campaign_id,
            tags=source.tags + ["forked"],
            category=source.category,
        )
        logger.info(f"Forked skill {source.name} → {forked.name} for campaign {campaign_id}")
        return forked


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

skillforge = SkillForge()
