"""
Omni OS Backend — Semantic Memory & RAG Pipeline
Provides vector-based memory storage and retrieval using cosine similarity.
Complements adaptation.py (metric-driven learning) and genome.py (cross-campaign DNA)
by adding free-text semantic recall: episodes, lessons, facts, and strategies.

Uses only stdlib + httpx. No numpy, no sklearn, no external vector DB.
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger("omnios.memory")

MemoryType = Literal["episode", "lesson", "fact", "strategy"]

# ═══════════════════════════════════════════════════════════════════════════════
# VECTOR MATH — pure-Python cosine similarity
# ═══════════════════════════════════════════════════════════════════════════════


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on degenerate input."""
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING PROVIDER — OpenAI API with bag-of-words fallback
# ═══════════════════════════════════════════════════════════════════════════════

# Stop words for the BoW fallback (common English words that carry little meaning)
_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could of in to for on with at by from as into "
    "through during before after above below between under again further then "
    "once here there when where why how all each every both few more most other "
    "some such no nor not only own same so than too very s t just don doesn didn "
    "it its he she they them their his her this that these those i me my we our "
    "you your what which who whom and but if or because until while about up out "
    "off over".split()
)


class EmbeddingProvider:
    """
    Generate text embeddings.
    - Primary: OpenAI text-embedding-3-small via httpx (if OPENAI_API_KEY set)
    - Fallback: deterministic bag-of-words hashing (zero external deps)

    Embeddings are cached by content hash to avoid redundant API calls.
    """

    OPENAI_DIM = 256  # request smaller dim for speed/cost
    BOW_DIM = 384     # fallback vector dimension

    def __init__(self):
        self._cache: collections.OrderedDict[str, list[float]] = collections.OrderedDict()
        self._cache_max = 2000
        self._openai_key: str | None = None
        self._checked_key = False

    def _get_openai_key(self) -> str | None:
        if not self._checked_key:
            self._checked_key = True
            self._openai_key = os.getenv("OPENAI_API_KEY", "") or None
        return self._openai_key

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:24]

    # ── Public API ──────────────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for *text*."""
        h = self._content_hash(text)
        if h in self._cache:
            self._cache.move_to_end(h)
            return self._cache[h]

        key = self._get_openai_key()
        vec: list[float] | None = None
        if key:
            vec = await self._embed_openai(text, key)

        if vec is None:
            vec = self._embed_bow(text)

        # Cache
        self._cache[h] = vec
        while len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

        return vec

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Uses OpenAI batch API when available."""
        key = self._get_openai_key()

        # Check cache first
        results: list[list[float] | None] = []
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            h = self._content_hash(text)
            if h in self._cache:
                self._cache.move_to_end(h)
                results.append(self._cache[h])
            else:
                results.append(None)
                uncached_indices.append(i)
                uncached_texts.append(text)

        if not uncached_texts:
            return results  # type: ignore[return-value]

        # Try OpenAI batch
        vecs: list[list[float]] | None = None
        if key:
            vecs = await self._embed_openai_batch(uncached_texts, key)

        if vecs is None:
            vecs = [self._embed_bow(t) for t in uncached_texts]

        for idx, vec in zip(uncached_indices, vecs):
            h = self._content_hash(texts[idx])
            self._cache[h] = vec
            while len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)
            results[idx] = vec

        return results  # type: ignore[return-value]

    # ── OpenAI embedding ────────────────────────────────────────────────────

    async def _embed_openai(self, text: str, api_key: str) -> list[float] | None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "text-embedding-3-small",
                        "input": text[:8000],
                        "dimensions": self.OPENAI_DIM,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
                logger.warning("OpenAI embedding failed: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("OpenAI embedding error: %s", e)
        return None

    async def _embed_openai_batch(self, texts: list[str], api_key: str) -> list[list[float]] | None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "text-embedding-3-small",
                        "input": [t[:8000] for t in texts],
                        "dimensions": self.OPENAI_DIM,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()["data"]
                    # Sort by index to ensure order matches input
                    data.sort(key=lambda d: d["index"])
                    return [d["embedding"] for d in data]
                logger.warning("OpenAI batch embedding failed: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("OpenAI batch embedding error: %s", e)
        return None

    # ── Bag-of-words fallback ───────────────────────────────────────────────

    def _embed_bow(self, text: str) -> list[float]:
        """
        Deterministic bag-of-words embedding using feature hashing.
        No vocabulary needed — works on any text with zero external deps.
        """
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

        vec = [0.0] * self.BOW_DIM

        # Feature hashing: map each token (+ bigrams) to vector positions
        for i, token in enumerate(tokens):
            # Unigram
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.BOW_DIM
            sign = 1.0 if (h // self.BOW_DIM) % 2 == 0 else -1.0
            vec[idx] += sign * 1.0

            # Bigram (token + next token)
            if i + 1 < len(tokens):
                bigram = f"{token}_{tokens[i + 1]}"
                h2 = int(hashlib.md5(bigram.encode()).hexdigest(), 16)
                idx2 = h2 % self.BOW_DIM
                sign2 = 1.0 if (h2 // self.BOW_DIM) % 2 == 0 else -1.0
                vec[idx2] += sign2 * 0.5

        # L2 normalize
        n = _norm(vec)
        if n > 0:
            vec = [x / n for x in vec]

        return vec


# Singleton
embedding_provider = EmbeddingProvider()


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC MEMORY — In-memory vector store with LRU eviction
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MemoryRecord:
    """A single memory entry with its embedding."""
    id: str
    type: MemoryType
    content: str
    embedding: list[float]
    campaign_id: str
    agent_id: str
    timestamp: str
    relevance_score: float = 0.5  # 0-1, decays over time, boosted on retrieval
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """
    In-memory vector store for semantic memories.
    - Cosine similarity search
    - Bounded storage with LRU eviction of oldest low-relevance memories
    - Partitioned by campaign_id for isolation
    """

    MAX_MEMORIES_PER_CAMPAIGN = 500
    EVICTION_TARGET = 400  # evict down to this when hitting max
    RELEVANCE_DECAY_RATE = 0.01  # per hour

    def __init__(self):
        # campaign_id -> list[MemoryRecord]
        self._store: dict[str, list[MemoryRecord]] = {}

    # ── Store ───────────────────────────────────────────────────────────────

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        campaign_id: str,
        agent_id: str = "",
        relevance_score: float = 0.5,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Store a new memory with its embedding."""
        embedding = await embedding_provider.embed(content)

        record = MemoryRecord(
            id=str(uuid.uuid4()),
            type=memory_type,
            content=content,
            embedding=embedding,
            campaign_id=campaign_id,
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            relevance_score=relevance_score,
            source=source,
            metadata=metadata or {},
        )

        memories = self._store.setdefault(campaign_id, [])
        memories.append(record)

        # Evict if over capacity
        if len(memories) > self.MAX_MEMORIES_PER_CAMPAIGN:
            self._evict(campaign_id)

        logger.debug(
            "Stored %s memory for campaign %s: %s",
            memory_type, campaign_id, content[:80],
        )
        return record

    async def store_batch(
        self,
        items: list[dict[str, Any]],
        campaign_id: str,
    ) -> list[MemoryRecord]:
        """Store multiple memories efficiently using batch embedding."""
        texts = [item["content"] for item in items]
        embeddings = await embedding_provider.embed_batch(texts)

        records = []
        memories = self._store.setdefault(campaign_id, [])

        for item, emb in zip(items, embeddings):
            record = MemoryRecord(
                id=str(uuid.uuid4()),
                type=item.get("type", "fact"),
                content=item["content"],
                embedding=emb,
                campaign_id=campaign_id,
                agent_id=item.get("agent_id", ""),
                timestamp=datetime.now(timezone.utc).isoformat(),
                relevance_score=item.get("relevance_score", 0.5),
                source=item.get("source", ""),
                metadata=item.get("metadata", {}),
            )
            memories.append(record)
            records.append(record)

        if len(memories) > self.MAX_MEMORIES_PER_CAMPAIGN:
            self._evict(campaign_id)

        return records

    # ── Retrieve ────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        campaign_id: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
        agent_id: str | None = None,
        min_similarity: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Search memories by semantic similarity to *query*."""
        memories = self._store.get(campaign_id, [])
        if not memories:
            return []

        query_vec = await embedding_provider.embed(query)

        scored: list[tuple[float, MemoryRecord]] = []
        now = datetime.now(timezone.utc)

        for mem in memories:
            # Filter by type
            if memory_types and mem.type not in memory_types:
                continue
            # Filter by agent
            if agent_id and mem.agent_id and mem.agent_id != agent_id:
                continue

            sim = cosine_similarity(query_vec, mem.embedding)
            if sim < min_similarity:
                continue

            # Boost by relevance score; decay by age
            try:
                mem_time = datetime.fromisoformat(mem.timestamp)
                age_hours = max((now - mem_time).total_seconds() / 3600, 0)
            except (ValueError, TypeError):
                age_hours = 0

            decay = max(0.1, 1.0 - self.RELEVANCE_DECAY_RATE * age_hours)
            final_score = sim * 0.7 + mem.relevance_score * 0.2 + decay * 0.1

            scored.append((final_score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Boost relevance_score of retrieved memories (reinforcement)
        results = []
        for score, mem in scored[:top_k]:
            mem.relevance_score = min(1.0, mem.relevance_score + 0.05)
            results.append({
                "id": mem.id,
                "type": mem.type,
                "content": mem.content,
                "campaign_id": mem.campaign_id,
                "agent_id": mem.agent_id,
                "timestamp": mem.timestamp,
                "relevance_score": mem.relevance_score,
                "similarity": round(score, 4),
                "source": mem.source,
                "metadata": mem.metadata,
            })

        return results

    def list_memories(
        self,
        campaign_id: str,
        memory_type: MemoryType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memories for a campaign, optionally filtered by type."""
        memories = self._store.get(campaign_id, [])

        if memory_type:
            memories = [m for m in memories if m.type == memory_type]

        # Sort by timestamp descending (newest first)
        memories.sort(key=lambda m: m.timestamp, reverse=True)

        page = memories[offset:offset + limit]
        return [
            {
                "id": m.id,
                "type": m.type,
                "content": m.content,
                "campaign_id": m.campaign_id,
                "agent_id": m.agent_id,
                "timestamp": m.timestamp,
                "relevance_score": m.relevance_score,
                "source": m.source,
                "metadata": m.metadata,
            }
            for m in page
        ]

    def clear(self, campaign_id: str) -> int:
        """Clear all memories for a campaign. Returns count deleted."""
        memories = self._store.pop(campaign_id, [])
        return len(memories)

    def count(self, campaign_id: str) -> int:
        return len(self._store.get(campaign_id, []))

    # ── LRU Eviction ────────────────────────────────────────────────────────

    def _evict(self, campaign_id: str) -> int:
        """Evict oldest low-relevance memories down to EVICTION_TARGET."""
        memories = self._store.get(campaign_id, [])
        if len(memories) <= self.EVICTION_TARGET:
            return 0

        # Score each memory: low relevance + old = evict first
        now = datetime.now(timezone.utc)

        def eviction_priority(m: MemoryRecord) -> float:
            """Lower = more likely to evict."""
            try:
                age_hours = (now - datetime.fromisoformat(m.timestamp)).total_seconds() / 3600
            except (ValueError, TypeError):
                age_hours = 1000
            # Lessons and strategies are more valuable — keep them longer
            type_bonus = {"lesson": 0.3, "strategy": 0.25, "fact": 0.1, "episode": 0.0}
            return m.relevance_score + type_bonus.get(m.type, 0) - (age_hours * 0.001)

        memories.sort(key=eviction_priority)
        to_remove = len(memories) - self.EVICTION_TARGET
        evicted = memories[:to_remove]
        self._store[campaign_id] = memories[to_remove:]

        logger.info(
            "Evicted %d memories from campaign %s (kept %d)",
            len(evicted), campaign_id, len(self._store[campaign_id]),
        )
        return len(evicted)


# Singleton
semantic_memory = SemanticMemory()


# ═══════════════════════════════════════════════════════════════════════════════
# RAG PIPELINE — Ingest, chunk, query, build context
# ═══════════════════════════════════════════════════════════════════════════════


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline:
    - Ingest: chunk text documents, embed, store as facts
    - Query: find relevant chunks for a question
    - Build context: auto-assemble relevant memories for an agent run
    """

    CHUNK_SIZE = 800       # characters per chunk
    CHUNK_OVERLAP = 100    # character overlap between chunks

    def __init__(self, memory: SemanticMemory | None = None):
        self._memory = memory or semantic_memory

    # ── Ingest ──────────────────────────────────────────────────────────────

    async def ingest(
        self,
        text: str,
        source: str,
        campaign_id: str,
        memory_type: MemoryType = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Chunk text, embed each chunk, store. Returns number of chunks stored."""
        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        items = []
        for i, chunk in enumerate(chunks):
            items.append({
                "content": chunk,
                "type": memory_type,
                "source": source,
                "relevance_score": 0.5,
                "metadata": {
                    **(metadata or {}),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })

        await self._memory.store_batch(items, campaign_id)
        logger.info("Ingested %d chunks from '%s' into campaign %s", len(chunks), source, campaign_id)
        return len(chunks)

    # ── Query ───────────────────────────────────────────────────────────────

    async def query(
        self,
        question: str,
        campaign_id: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> str:
        """
        Find relevant chunks for a question. Returns a formatted context string
        suitable for injection into an LLM prompt.
        """
        results = await self._memory.search(
            query=question,
            campaign_id=campaign_id,
            top_k=top_k,
            memory_types=memory_types,
        )

        if not results:
            return ""

        lines = []
        for r in results:
            src = f" (source: {r['source']})" if r.get("source") else ""
            lines.append(f"[{r['type']}]{src}: {r['content']}")

        return "\n---\n".join(lines)

    # ── Build Agent Context ─────────────────────────────────────────────────

    async def build_context(
        self,
        agent_id: str,
        campaign_id: str,
        goal_hint: str = "",
        max_tokens_estimate: int = 1500,
    ) -> str:
        """
        Auto-build relevant context for an agent run by querying:
        1. Past episodes from this agent
        2. Lessons learned
        3. Relevant strategies
        4. Facts related to the agent's goal

        Returns a formatted prompt block.
        """
        sections: list[str] = []

        # 1. Recent episodes from this agent
        episodes = await self._memory.search(
            query=f"What happened when {agent_id} ran previously?",
            campaign_id=campaign_id,
            top_k=3,
            memory_types=["episode"],
            agent_id=agent_id,
        )
        if episodes:
            ep_lines = [f"- {e['content'][:200]}" for e in episodes]
            sections.append("Past episodes:\n" + "\n".join(ep_lines))

        # 2. Lessons learned (any agent)
        lessons = await self._memory.search(
            query=f"lessons learned for {agent_id} marketing campaign",
            campaign_id=campaign_id,
            top_k=3,
            memory_types=["lesson"],
        )
        if lessons:
            ls_lines = [f"- {ls['content'][:200]}" for ls in lessons]
            sections.append("Lessons learned:\n" + "\n".join(ls_lines))

        # 3. Strategies
        strategies = await self._memory.search(
            query=f"effective strategy for {agent_id}",
            campaign_id=campaign_id,
            top_k=2,
            memory_types=["strategy"],
        )
        if strategies:
            st_lines = [f"- {s['content'][:200]}" for s in strategies]
            sections.append("Known strategies:\n" + "\n".join(st_lines))

        # 4. Goal-relevant facts
        if goal_hint:
            facts = await self._memory.search(
                query=goal_hint,
                campaign_id=campaign_id,
                top_k=3,
                memory_types=["fact"],
            )
            if facts:
                f_lines = [f"- {f['content'][:200]}" for f in facts]
                sections.append("Relevant context:\n" + "\n".join(f_lines))

        if not sections:
            return ""

        # Truncate to approximate token budget
        context = "\n\n".join(sections)
        # Rough estimate: 1 token ~ 4 chars
        max_chars = max_tokens_estimate * 4
        if len(context) > max_chars:
            context = context[:max_chars] + "\n[... truncated]"

        return (
            "=== SEMANTIC MEMORY (relevant past knowledge) ===\n"
            + context
            + "\n================================================="
        )

    # ── Text Chunking ───────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks at sentence/paragraph boundaries."""
        if not text or not text.strip():
            return []

        text = text.strip()

        # If short enough, return as single chunk
        if len(text) <= self.CHUNK_SIZE:
            return [text]

        # Split on paragraph boundaries first, then sentences
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 1 <= self.CHUNK_SIZE:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                # If paragraph itself is too long, split by sentences
                if len(para) > self.CHUNK_SIZE:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    sub_chunk = ""
                    for sent in sentences:
                        if len(sub_chunk) + len(sent) + 1 <= self.CHUNK_SIZE:
                            sub_chunk = (sub_chunk + " " + sent).strip()
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            # If single sentence is too long, hard split
                            if len(sent) > self.CHUNK_SIZE:
                                for i in range(0, len(sent), self.CHUNK_SIZE - self.CHUNK_OVERLAP):
                                    chunks.append(sent[i:i + self.CHUNK_SIZE])
                                sub_chunk = ""
                            else:
                                sub_chunk = sent
                    if sub_chunk:
                        current = sub_chunk
                    else:
                        current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return chunks


# Singleton
rag_pipeline = RAGPipeline()


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINE INTEGRATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


async def extract_and_store_memories(
    agent_id: str,
    campaign_id: str,
    output: str,
    memory_update: dict[str, Any],
) -> int:
    """
    Called after an agent run completes. Extracts and stores:
    - An episode summarizing what happened
    - Lessons extracted from the output
    Returns count of memories stored.
    """
    if not output or not output.strip():
        return 0

    count = 0

    # 1. Store episode: a concise summary of what the agent did
    episode_summary = output[:500]
    if len(output) > 500:
        episode_summary += "..."

    await semantic_memory.store(
        content=f"Agent '{agent_id}' produced: {episode_summary}",
        memory_type="episode",
        campaign_id=campaign_id,
        agent_id=agent_id,
        relevance_score=0.6,
        source=f"agent_run:{agent_id}",
    )
    count += 1

    # 2. Store any extracted memory fields as facts
    if memory_update:
        for key, value in memory_update.items():
            if not value:
                continue
            val_str = value if isinstance(value, str) else json.dumps(value, default=str)
            if len(val_str) > 50:  # skip trivially short values
                await semantic_memory.store(
                    content=f"{key}: {val_str[:600]}",
                    memory_type="fact",
                    campaign_id=campaign_id,
                    agent_id=agent_id,
                    relevance_score=0.5,
                    source=f"agent_run:{agent_id}",
                    metadata={"memory_key": key},
                )
                count += 1

    # 3. Try to extract lessons — look for patterns in output
    lesson_patterns = [
        r"(?i)(?:lesson|learning|insight|takeaway|key finding)[s]?\s*[:—\-]\s*(.{30,300})",
        r"(?i)(?:what worked|success|effective)[s]?\s*[:—\-]\s*(.{30,300})",
        r"(?i)(?:recommendation|suggest|should)\s*[:—\-]\s*(.{30,300})",
    ]
    for pattern in lesson_patterns:
        matches = re.findall(pattern, output)
        for match in matches[:3]:  # max 3 lessons per pattern
            await semantic_memory.store(
                content=match.strip(),
                memory_type="lesson",
                campaign_id=campaign_id,
                agent_id=agent_id,
                relevance_score=0.7,
                source=f"agent_run:{agent_id}",
            )
            count += 1

    logger.info("Extracted %d memories from agent %s in campaign %s", count, agent_id, campaign_id)
    return count


async def build_memory_context(
    agent_id: str,
    campaign_id: str,
    goal_hint: str = "",
) -> str:
    """
    Called before an agent run starts. Queries semantic memory for relevant
    context and returns a prompt block for injection.
    """
    if not campaign_id:
        return ""

    try:
        context = await rag_pipeline.build_context(
            agent_id=agent_id,
            campaign_id=campaign_id,
            goal_hint=goal_hint,
        )
        return context
    except Exception as e:
        logger.warning("Failed to build memory context for %s: %s", agent_id, e)
        return ""
