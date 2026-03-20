"""
Omni OS Backend — Wide Research: Parallel Sub-Agent Spawning
Spawn N full-capability agents in parallel for a single research task.
Competes with Manus's Wide Research where every sub-agent is a full instance.
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("supervisor.wideresearch")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchQuery(BaseModel):
    """A single research sub-query to be executed by a sub-agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str
    focus_area: str = ""           # e.g., "pricing", "features", "reviews", "technical"
    sources_to_check: list[str] = []  # Specific URLs or domains to prioritize
    max_depth: int = 3             # How deep to follow links
    status: str = "pending"        # pending | running | completed | failed
    result: str = ""
    sources_found: list[str] = []
    confidence: float = 0.0        # 0-1 confidence in the result
    execution_time_ms: int = 0


class WideResearchJob(BaseModel):
    """A wide research job that spawns multiple parallel sub-agents."""
    id: str = Field(default_factory=lambda: f"wr_{uuid.uuid4().hex[:12]}")
    campaign_id: str = ""
    user_id: str = ""
    topic: str                     # The main research question
    sub_queries: list[ResearchQuery] = []
    max_parallel: int = 5          # Max concurrent sub-agents
    status: str = "pending"        # pending | decomposing | researching | synthesizing | completed | failed
    synthesis: str = ""            # Final synthesized report
    total_sources: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0


class ResearchSynthesis(BaseModel):
    """Synthesized output from wide research."""
    job_id: str
    topic: str
    summary: str = ""
    key_findings: list[str] = []
    data_points: list[dict] = []   # Structured data extracted
    sources: list[str] = []
    confidence: float = 0.0
    methodology: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY DECOMPOSER
# ═══════════════════════════════════════════════════════════════════════════════

class QueryDecomposer:
    """
    Breaks a broad research question into specific sub-queries
    that can be executed in parallel by independent agents.
    """

    # Pre-built decomposition strategies
    STRATEGIES = {
        "competitor_analysis": [
            {"focus": "product_features", "template": "What are the key features and capabilities of {target}?"},
            {"focus": "pricing", "template": "What is the pricing model and plans for {target}?"},
            {"focus": "market_position", "template": "What is {target}'s market position, funding, and growth trajectory?"},
            {"focus": "strengths_weaknesses", "template": "What do users say about {target}? What are common complaints and praise?"},
            {"focus": "technology", "template": "What technology stack and architecture does {target} use?"},
        ],
        "market_research": [
            {"focus": "market_size", "template": "What is the total addressable market size for {topic}?"},
            {"focus": "trends", "template": "What are the key trends and drivers in {topic}?"},
            {"focus": "key_players", "template": "Who are the major players in {topic} and what are their market shares?"},
            {"focus": "customer_segments", "template": "What are the primary customer segments for {topic}?"},
            {"focus": "regulations", "template": "What regulations and compliance requirements affect {topic}?"},
        ],
        "technical_research": [
            {"focus": "architecture", "template": "What are the common architecture patterns for {topic}?"},
            {"focus": "tools_frameworks", "template": "What tools and frameworks are most used for {topic}?"},
            {"focus": "best_practices", "template": "What are the current best practices for {topic}?"},
            {"focus": "benchmarks", "template": "What are the latest benchmarks and performance data for {topic}?"},
            {"focus": "open_source", "template": "What open source projects are available for {topic}?"},
        ],
        "general": [
            {"focus": "overview", "template": "Provide a comprehensive overview of {topic}"},
            {"focus": "current_state", "template": "What is the current state of {topic} in 2026?"},
            {"focus": "key_players", "template": "Who are the key people, companies, and organizations in {topic}?"},
            {"focus": "challenges", "template": "What are the main challenges and problems in {topic}?"},
            {"focus": "future", "template": "What is the future outlook for {topic}?"},
        ],
    }

    def decompose(self, topic: str, strategy: str = "general",
                  custom_queries: list[str] = None,
                  targets: list[str] = None) -> list[ResearchQuery]:
        """
        Decompose a topic into parallel research queries.
        """
        queries = []

        if custom_queries:
            # Use user-provided queries
            for q in custom_queries:
                queries.append(ResearchQuery(query=q, focus_area="custom"))
        elif targets:
            # Apply strategy template to each target
            templates = self.STRATEGIES.get(strategy, self.STRATEGIES["general"])
            for target in targets:
                for tmpl in templates:
                    query_text = tmpl["template"].format(target=target, topic=target)
                    queries.append(ResearchQuery(
                        query=query_text, focus_area=f"{target}_{tmpl['focus']}",
                    ))
        else:
            # Apply strategy to the topic
            templates = self.STRATEGIES.get(strategy, self.STRATEGIES["general"])
            for tmpl in templates:
                query_text = tmpl["template"].format(topic=topic, target=topic)
                queries.append(ResearchQuery(
                    query=query_text, focus_area=tmpl["focus"],
                ))

        logger.info(f"Decomposed '{topic}' into {len(queries)} sub-queries using {strategy} strategy")
        return queries


# ═══════════════════════════════════════════════════════════════════════════════
# WIDE RESEARCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class WideResearchEngine:
    """
    Orchestrates parallel sub-agent research.
    Each sub-agent gets the full tool suite and runs independently.
    Results are synthesized into a unified report.
    """

    def __init__(self):
        self.decomposer = QueryDecomposer()
        self._jobs: dict[str, WideResearchJob] = {}
        self._results_cache: dict[str, ResearchSynthesis] = {}

    def create_job(self, topic: str, campaign_id: str = "", user_id: str = "",
                   strategy: str = "general", max_parallel: int = 5,
                   custom_queries: list[str] = None,
                   targets: list[str] = None) -> WideResearchJob:
        """Create a wide research job with decomposed sub-queries."""
        queries = self.decomposer.decompose(
            topic, strategy=strategy,
            custom_queries=custom_queries, targets=targets,
        )

        job = WideResearchJob(
            campaign_id=campaign_id, user_id=user_id,
            topic=topic, sub_queries=queries,
            max_parallel=min(max_parallel, 10),  # Cap at 10
        )

        self._jobs[job.id] = job
        logger.info(f"Created wide research job {job.id}: {len(queries)} sub-queries")
        return job

    async def execute(self, job_id: str, agent_runner=None,
                      tool_registry=None, llm_router=None) -> WideResearchJob:
        """
        Execute all sub-queries in parallel using the agent engine.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "researching"
        job.started_at = datetime.utcnow()
        start = time.time()

        # Execute sub-queries in parallel batches
        semaphore = asyncio.Semaphore(job.max_parallel)

        async def run_query(query: ResearchQuery) -> ResearchQuery:
            async with semaphore:
                query.status = "running"
                q_start = time.time()
                try:
                    result = await self._execute_single_query(
                        query, tool_registry, llm_router,
                    )
                    query.result = result.get("text", "")
                    query.sources_found = result.get("sources", [])
                    query.confidence = result.get("confidence", 0.5)
                    query.status = "completed"
                except Exception as e:
                    query.result = f"Error: {e}"
                    query.status = "failed"
                    logger.error(f"Sub-query failed: {query.query[:50]}... → {e}")

                query.execution_time_ms = int((time.time() - q_start) * 1000)
                return query

        # Run all queries concurrently (bounded by semaphore)
        await asyncio.gather(*[run_query(q) for q in job.sub_queries])

        # Synthesize results
        job.status = "synthesizing"
        synthesis = await self._synthesize(job, llm_router)
        job.synthesis = synthesis.summary if synthesis else ""
        job.total_sources = sum(len(q.sources_found) for q in job.sub_queries)

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.execution_time_ms = int((time.time() - start) * 1000)

        if synthesis:
            self._results_cache[job.id] = synthesis

        logger.info(f"Wide research {job.id} completed: {job.execution_time_ms}ms, "
                     f"{job.total_sources} sources")
        return job

    async def _execute_single_query(self, query: ResearchQuery,
                                     tool_registry, llm_router) -> dict:
        """Execute a single research sub-query using available tools."""
        if not llm_router:
            return {"text": f"[No LLM available] Query: {query.query}", "sources": [], "confidence": 0}

        # Build a research-focused prompt
        prompt = (
            f"You are a research agent. Answer this question thoroughly with specific data:\n\n"
            f"{query.query}\n\n"
            f"Focus area: {query.focus_area}\n"
            f"Include specific numbers, dates, and sources where possible. "
            f"Be concise but comprehensive."
        )

        # Use tools if available
        tools = None
        if tool_registry:
            tools = tool_registry.get_definitions(categories=["web", "prospecting"])

        result = await llm_router.complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are a thorough research analyst. Provide specific, data-driven answers.",
            tools=tools,
            max_tokens=2048,
        )

        return {
            "text": result.get("text", ""),
            "sources": query.sources_to_check,
            "confidence": 0.7,
        }

    async def _synthesize(self, job: WideResearchJob,
                           llm_router) -> Optional[ResearchSynthesis]:
        """Synthesize all sub-query results into a unified report."""
        completed = [q for q in job.sub_queries if q.status == "completed" and q.result]
        if not completed:
            return None

        # Build synthesis prompt
        findings = "\n\n".join(
            f"### {q.focus_area}\n{q.result}"
            for q in completed
        )

        prompt = (
            f"You are synthesizing research on: {job.topic}\n\n"
            f"Below are findings from {len(completed)} parallel research agents:\n\n"
            f"{findings}\n\n"
            f"Synthesize these into a unified, well-structured report with:\n"
            f"1. Executive summary (2-3 sentences)\n"
            f"2. Key findings (bullet points)\n"
            f"3. Detailed analysis organized by theme\n"
            f"4. Data points and statistics\n"
            f"5. Recommendations\n\n"
            f"Resolve any contradictions between sources. Note confidence levels."
        )

        if llm_router:
            result = await llm_router.complete(
                messages=[{"role": "user", "content": prompt}],
                system="You are a senior research analyst synthesizing multi-source intelligence.",
                max_tokens=4096,
            )
            summary = result.get("text", "")
        else:
            summary = findings

        all_sources = []
        for q in completed:
            all_sources.extend(q.sources_found)

        avg_confidence = (
            sum(q.confidence for q in completed) / len(completed)
            if completed else 0
        )

        return ResearchSynthesis(
            job_id=job.id, topic=job.topic,
            summary=summary,
            key_findings=[q.result[:200] for q in completed[:10]],
            sources=list(set(all_sources)),
            confidence=avg_confidence,
            methodology=f"Wide Research: {len(completed)} parallel agents, "
                        f"{len(job.sub_queries) - len(completed)} failed",
        )

    def get_job(self, job_id: str) -> Optional[WideResearchJob]:
        return self._jobs.get(job_id)

    def get_synthesis(self, job_id: str) -> Optional[ResearchSynthesis]:
        return self._results_cache.get(job_id)

    def list_jobs(self, campaign_id: str = None, user_id: str = None) -> list[WideResearchJob]:
        jobs = list(self._jobs.values())
        if campaign_id:
            jobs = [j for j in jobs if j.campaign_id == campaign_id]
        if user_id:
            jobs = [j for j in jobs if j.user_id == user_id]
        return sorted(jobs, key=lambda j: j.started_at or datetime.min, reverse=True)

    def get_available_strategies(self) -> list[dict]:
        return [
            {"name": name, "query_count": len(templates),
             "focus_areas": [t["focus"] for t in templates]}
            for name, templates in QueryDecomposer.STRATEGIES.items()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

wide_research = WideResearchEngine()
