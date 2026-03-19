"""
Omni OS Backend — Multi-Provider Model Router
Failover: Anthropic → OpenAI → Google. Normalizes tool calling across all three.
"""
from __future__ import annotations
import json
import time
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from config import ProviderConfig, settings
from models import ToolCall, ToolDefinition, Tier

logger = logging.getLogger("omnios.router")


class ProviderError(Exception):
    def __init__(self, reason: str, provider: str):
        self.reason = reason
        self.provider = provider
        super().__init__(f"[{provider}] {reason}")


class AllProvidersFailedError(Exception):
    def __init__(self, errors: list[ProviderError]):
        self.errors = errors
        providers = ", ".join(f"{e.provider}({e.reason})" for e in errors)
        super().__init__(f"All providers failed: {providers}")


# ═══════════════════════════════════════════════════════════════════════════════
# BASE ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitState:
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped -- reject all requests
    HALF_OPEN = "half_open"  # Allow one probe request


class ProviderAdapter:
    # Circuit breaker thresholds
    CB_FAILURE_THRESHOLD = 5    # Errors before circuit opens
    CB_RESET_TIMEOUT = 60.0     # Seconds before half-open probe
    CB_SUCCESS_THRESHOLD = 2    # Successes in half-open to close

    # Per-provider rate limits (requests per minute)
    RATE_LIMITS = {
        "anthropic": 60,
        "openai": 60,
        "google": 60,
        "bedrock": 30,
    }

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self._error_count = 0
        self._last_error: Optional[str] = None
        self._cooldown_until = 0.0
        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._circuit_opened_at = 0.0
        self._half_open_successes = 0
        # Per-provider rate limiting
        self._request_timestamps: list[float] = []
        self._rate_limit = self.RATE_LIMITS.get(config.name, 60)

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits. Prunes old timestamps."""
        now = time.time()
        cutoff = now - 60.0  # 1-minute window
        self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]
        if len(self._request_timestamps) >= self._rate_limit:
            return False
        self._request_timestamps.append(now)
        return True

    @property
    def is_available(self) -> bool:
        if not self.config.enabled:
            return False
        now = time.time()
        if self._circuit_state == CircuitState.OPEN:
            if now - self._circuit_opened_at >= self.CB_RESET_TIMEOUT:
                self._circuit_state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                logger.info(f"[{self.config.name}] Circuit half-open, allowing probe")
                return True
            return False
        if not self._check_rate_limit():
            logger.warning(f"[{self.config.name}] Rate limit reached ({self._rate_limit}/min)")
            return False
        return now >= self._cooldown_until

    def _mark_error(self, error: str):
        self._error_count += 1
        self._last_error = error
        cooldown = min(5 * (3 ** (self._error_count - 1)), 120)
        self._cooldown_until = time.time() + cooldown

        if self._circuit_state == CircuitState.HALF_OPEN:
            self._circuit_state = CircuitState.OPEN
            self._circuit_opened_at = time.time()
            logger.warning(f"[{self.config.name}] Half-open probe failed, circuit re-opened")
        elif self._error_count >= self.CB_FAILURE_THRESHOLD:
            self._circuit_state = CircuitState.OPEN
            self._circuit_opened_at = time.time()
            logger.warning(f"[{self.config.name}] Circuit OPEN after {self._error_count} errors")
        else:
            logger.warning(f"[{self.config.name}] Error #{self._error_count}: {error}. Cooldown {cooldown}s")

    def _mark_success(self):
        if self._circuit_state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.CB_SUCCESS_THRESHOLD:
                self._circuit_state = CircuitState.CLOSED
                self._error_count = 0
                self._last_error = None
                self._cooldown_until = 0.0
                logger.info(f"[{self.config.name}] Circuit CLOSED after successful probes")
                return
        self._error_count = 0
        self._last_error = None
        self._cooldown_until = 0.0
        if self._circuit_state != CircuitState.HALF_OPEN:
            self._circuit_state = CircuitState.CLOSED

    def get_model(self, tier: Tier, model_override: str = None) -> str:
        if model_override:
            return model_override
        if tier == Tier.FAST:
            return self.config.fast_model
        if tier == Tier.STRONG and self.config.strong_model:
            return self.config.strong_model
        return self.config.default_model

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None) -> dict:
        raise NotImplementedError

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None) -> AsyncGenerator[dict, None]:
        raise NotImplementedError
        yield  # pragma: no cover

    def status(self) -> dict:
        return {
            "name": self.config.name, "enabled": self.config.enabled,
            "available": self.is_available, "model": self.config.default_model,
            "fast_model": self.config.fast_model, "error_count": self._error_count,
            "last_error": self._last_error,
            "circuit_state": self._circuit_state,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ANTHROPIC ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class AnthropicAdapter(ProviderAdapter):

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [t.to_anthropic_schema() for t in tools]
        try:
            resp = await self.client.post(
                f"{self.config.base_url}/v1/messages",
                headers={"x-api-key": self.config.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json=body,
            )
            if resp.status_code in (429, 529):
                self._mark_error("rate_limited")
                raise ProviderError("rate_limited", self.config.name)
            if resp.status_code >= 500:
                self._mark_error(f"server_{resp.status_code}")
                raise ProviderError(f"server_{resp.status_code}", self.config.name)
            resp.raise_for_status()
            data = resp.json()
            self._mark_success()
            return self._normalize(data, model)
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)
        except httpx.HTTPStatusError as e:
            self._mark_error(str(e))
            raise ProviderError(str(e), self.config.name)

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages, "stream": True}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [t.to_anthropic_schema() for t in tools]
        try:
            async with self.client.stream(
                "POST", f"{self.config.base_url}/v1/messages",
                headers={"x-api-key": self.config.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json=body,
            ) as resp:
                if resp.status_code in (429, 529):
                    self._mark_error("rate_limited")
                    raise ProviderError("rate_limited", self.config.name)
                if resp.status_code >= 500:
                    self._mark_error(f"server_{resp.status_code}")
                    raise ProviderError(f"server_{resp.status_code}", self.config.name)

                current_tc = None
                tc_json = ""
                _stream_usage: dict[str, int] = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:].strip())
                    except json.JSONDecodeError:
                        continue
                    et = ev.get("type", "")
                    if et == "content_block_start":
                        blk = ev.get("content_block", {})
                        if blk.get("type") == "tool_use":
                            current_tc = {"id": blk["id"], "name": blk["name"]}
                            tc_json = ""
                    elif et == "content_block_delta":
                        d = ev.get("delta", {})
                        if d.get("type") == "text_delta":
                            yield {"type": "text", "text": d["text"], "provider": self.config.name, "model": model}
                        elif d.get("type") == "input_json_delta":
                            tc_json += d.get("partial_json", "")
                    elif et == "content_block_stop":
                        if current_tc:
                            try:
                                inp = json.loads(tc_json) if tc_json else {}
                            except json.JSONDecodeError:
                                inp = {}
                            yield {"type": "tool_call", "tool_call": ToolCall(id=current_tc["id"], name=current_tc["name"], input=inp), "provider": self.config.name, "model": model}
                            current_tc = None
                            tc_json = ""
                    elif et == "message_delta":
                        usage = ev.get("usage", {})
                        if usage:
                            _stream_usage["output_tokens"] = usage.get("output_tokens", 0)
                    elif et == "message_start":
                        msg = ev.get("message", {})
                        _stream_usage.update(msg.get("usage", {}))
                    elif et == "message_stop":
                        yield {"type": "done", "provider": self.config.name, "model": model, "usage": _stream_usage}
                self._mark_success()
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)

    def _normalize(self, data: dict, model: str) -> dict:
        text_parts, tool_calls = [], []
        for blk in data.get("content", []):
            if blk["type"] == "text":
                text_parts.append(blk["text"])
            elif blk["type"] == "tool_use":
                tool_calls.append(ToolCall(id=blk["id"], name=blk["name"], input=blk.get("input", {})))
        return {"text": "".join(text_parts), "tool_calls": tool_calls, "stop_reason": data.get("stop_reason", ""), "provider": self.config.name, "model": model, "usage": data.get("usage", {})}


# ═══════════════════════════════════════════════════════════════════════════════
# OPENAI ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class OpenAIAdapter(ProviderAdapter):

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _convert_msgs(self, messages: list[dict], system: str) -> list[dict]:
        out = []
        if system:
            out.append({"role": "system", "content": system})
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "tool_result":
                out.append({"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": content if isinstance(content, str) else json.dumps(content)})
            elif role == "user" and isinstance(content, list):
                # Handle Anthropic-style tool_result wrapped in user message
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        out.append({"role": "tool", "tool_call_id": block.get("tool_use_id", ""), "content": block.get("content", "")})
                    else:
                        out.append({"role": "user", "content": block if isinstance(block, str) else json.dumps(block)})
            elif role == "assistant" and isinstance(content, list):
                text_parts, oai_tcs = [], []
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        text_parts.append(blk["text"])
                    elif isinstance(blk, dict) and blk.get("type") == "tool_use":
                        oai_tcs.append({"id": blk["id"], "type": "function", "function": {"name": blk["name"], "arguments": json.dumps(blk.get("input", {}))}})
                oai_msg: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    oai_msg["content"] = "".join(text_parts)
                if oai_tcs:
                    oai_msg["tool_calls"] = oai_tcs
                out.append(oai_msg)
            else:
                out.append({"role": role, "content": content})
        return out

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        converted = self._convert_msgs(messages, system)
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": converted}
        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]
        try:
            resp = await self.client.post(
                f"{self.config.base_url}/v1/chat/completions",
                headers=self._get_headers(),
                json=body,
            )
            if resp.status_code == 429:
                self._mark_error("rate_limited")
                raise ProviderError("rate_limited", self.config.name)
            if resp.status_code >= 500:
                self._mark_error(f"server_{resp.status_code}")
                raise ProviderError(f"server_{resp.status_code}", self.config.name)
            resp.raise_for_status()
            data = resp.json()
            self._mark_success()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            text = msg.get("content", "") or ""
            tcs = []
            for tc in msg.get("tool_calls", []):
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}
                tcs.append(ToolCall(id=tc["id"], name=tc["function"]["name"], input=args))
            return {"text": text, "tool_calls": tcs, "stop_reason": choice.get("finish_reason", ""), "provider": self.config.name, "model": model, "usage": data.get("usage", {})}
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        converted = self._convert_msgs(messages, system)
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": converted, "stream": True,
                                "stream_options": {"include_usage": True}}
        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]
        try:
            async with self.client.stream(
                "POST", f"{self.config.base_url}/v1/chat/completions",
                headers=self._get_headers(),
                json=body,
            ) as resp:
                if resp.status_code == 429:
                    self._mark_error("rate_limited")
                    raise ProviderError("rate_limited", self.config.name)
                if resp.status_code >= 500:
                    self._mark_error(f"server_{resp.status_code}")
                    raise ProviderError(f"server_{resp.status_code}", self.config.name)

                tc_buf: dict[int, dict] = {}
                _stream_usage: dict[str, int] = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        for idx in sorted(tc_buf.keys()):
                            tc = tc_buf[idx]
                            try:
                                parsed = json.loads(tc.get("arguments", "{}"))
                            except json.JSONDecodeError:
                                parsed = {}
                            yield {"type": "tool_call", "tool_call": ToolCall(id=tc["id"], name=tc["name"], input=parsed), "provider": self.config.name, "model": model}
                        yield {"type": "done", "provider": self.config.name, "model": model, "usage": _stream_usage}
                        break
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    # OpenAI includes usage in the final chunk when stream_options.include_usage is set
                    if ev.get("usage"):
                        u = ev["usage"]
                        _stream_usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}
                    choices = ev.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    if delta.get("content"):
                        yield {"type": "text", "text": delta["content"], "provider": self.config.name, "model": model}
                    if delta.get("tool_calls"):
                        for tcd in delta["tool_calls"]:
                            idx = tcd.get("index", 0)
                            if idx not in tc_buf:
                                tc_buf[idx] = {"id": "", "name": "", "arguments": ""}
                            if tcd.get("id"):
                                tc_buf[idx]["id"] = tcd["id"]
                            if tcd.get("function", {}).get("name"):
                                tc_buf[idx]["name"] = tcd["function"]["name"]
                            if tcd.get("function", {}).get("arguments"):
                                tc_buf[idx]["arguments"] += tcd["function"]["arguments"]
                self._mark_success()
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE GEMINI ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class GoogleAdapter(ProviderAdapter):

    def _convert_msgs(self, messages: list[dict], system: str):
        sys_inst = {"parts": [{"text": system}]} if system else None
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            content = msg.get("content", "")
            if msg["role"] == "tool_result" or (isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)):
                # Handle tool results
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            contents.append({"role": "function", "parts": [{"functionResponse": {"name": "tool", "response": {"result": block.get("content", "")}}}]})
                else:
                    contents.append({"role": "function", "parts": [{"functionResponse": {"name": msg.get("tool_name", "tool"), "response": {"result": content}}}]})
            elif isinstance(content, str):
                contents.append({"role": role, "parts": [{"text": content}]})
            elif isinstance(content, list):
                parts = []
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        parts.append({"text": blk["text"]})
                    elif isinstance(blk, dict) and blk.get("type") == "tool_use":
                        parts.append({"functionCall": {"name": blk["name"], "args": blk.get("input", {})}})
                if parts:
                    contents.append({"role": role, "parts": parts})
        return contents, sys_inst

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        contents, sys_inst = self._convert_msgs(messages, system)
        body: dict[str, Any] = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens}}
        if sys_inst:
            body["systemInstruction"] = sys_inst
        if tools:
            body["tools"] = [{"functionDeclarations": [t.to_google_schema() for t in tools]}]
        try:
            resp = await self.client.post(
                f"{self.config.base_url}/v1beta/models/{model}:generateContent",
                params={"key": self.config.api_key}, headers={"Content-Type": "application/json"}, json=body,
            )
            if resp.status_code == 429:
                self._mark_error("rate_limited")
                raise ProviderError("rate_limited", self.config.name)
            if resp.status_code >= 500:
                self._mark_error(f"server_{resp.status_code}")
                raise ProviderError(f"server_{resp.status_code}", self.config.name)
            resp.raise_for_status()
            data = resp.json()
            self._mark_success()
            candidates = data.get("candidates", [])
            if not candidates:
                return {"text": "", "tool_calls": [], "stop_reason": "", "provider": self.config.name, "model": model, "usage": {}}
            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts, tcs = [], []
            for p in parts:
                if "text" in p:
                    text_parts.append(p["text"])
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    tcs.append(ToolCall(name=fc["name"], input=fc.get("args", {})))
            return {"text": "".join(text_parts), "tool_calls": tcs, "stop_reason": candidates[0].get("finishReason", ""), "provider": self.config.name, "model": model, "usage": data.get("usageMetadata", {})}
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        model = self.get_model(tier, model_override)
        contents, sys_inst = self._convert_msgs(messages, system)
        body: dict[str, Any] = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens}}
        if sys_inst:
            body["systemInstruction"] = sys_inst
        if tools:
            body["tools"] = [{"functionDeclarations": [t.to_google_schema() for t in tools]}]
        try:
            async with self.client.stream(
                "POST", f"{self.config.base_url}/v1beta/models/{model}:streamGenerateContent",
                params={"key": self.config.api_key, "alt": "sse"}, headers={"Content-Type": "application/json"}, json=body,
            ) as resp:
                if resp.status_code == 429:
                    self._mark_error("rate_limited")
                    raise ProviderError("rate_limited", self.config.name)
                _stream_usage: dict[str, int] = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    # Google returns usageMetadata in the final chunk
                    um = ev.get("usageMetadata")
                    if um:
                        _stream_usage = {"input_tokens": um.get("promptTokenCount", 0), "output_tokens": um.get("candidatesTokenCount", 0)}
                    cands = ev.get("candidates", [])
                    if not cands:
                        continue
                    for p in cands[0].get("content", {}).get("parts", []):
                        if "text" in p:
                            yield {"type": "text", "text": p["text"], "provider": self.config.name, "model": model}
                        elif "functionCall" in p:
                            fc = p["functionCall"]
                            yield {"type": "tool_call", "tool_call": ToolCall(name=fc["name"], input=fc.get("args", {})), "provider": self.config.name, "model": model}
                yield {"type": "done", "provider": self.config.name, "model": model, "usage": _stream_usage}
                self._mark_success()
        except httpx.TimeoutException:
            self._mark_error("timeout")
            raise ProviderError("timeout", self.config.name)


# ═══════════════════════════════════════════════════════════════════════════════
# AWS BEDROCK ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class BedrockAdapter(ProviderAdapter):
    """AWS Bedrock — Claude, Llama, Mistral via AWS managed endpoints."""

    BEDROCK_MODELS = {
        "claude-sonnet": "anthropic.claude-sonnet-4-20250514-v1:0",
        "claude-haiku": "anthropic.claude-haiku-4-5-20251001-v1:0",
        "llama3-70b": "meta.llama3-70b-instruct-v1:0",
        "mistral-large": "mistral.mistral-large-2407-v1:0",
    }

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._boto_client = None

    def _get_boto_client(self):
        if self._boto_client:
            return self._boto_client
        try:
            import boto3
            import os
            region = os.getenv("AWS_BEDROCK_REGION", "us-east-1")
            self._boto_client = boto3.client("bedrock-runtime", region_name=region)
            return self._boto_client
        except ImportError:
            logger.warning("boto3 not installed — Bedrock unavailable")
            return None
        except Exception as e:
            logger.error(f"Bedrock client init failed: {e}")
            return None

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        client = self._get_boto_client()
        if not client:
            raise ProviderError("boto3_unavailable", self.config.name)

        model = self.get_model(tier, model_override)
        model_id = self.BEDROCK_MODELS.get(model, model)

        try:
            if "anthropic" in model_id:
                body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": max_tokens, "messages": messages}
                if system:
                    body["system"] = system
                if tools:
                    body["tools"] = [t.to_anthropic_schema() for t in tools]

                resp = client.invoke_model(modelId=model_id, body=json.dumps(body), contentType="application/json")
                data = json.loads(resp["body"].read())
                self._mark_success()

                text_parts, tool_calls = [], []
                for blk in data.get("content", []):
                    if blk["type"] == "text":
                        text_parts.append(blk["text"])
                    elif blk["type"] == "tool_use":
                        tool_calls.append(ToolCall(id=blk["id"], name=blk["name"], input=blk.get("input", {})))

                return {"text": "".join(text_parts), "tool_calls": tool_calls, "stop_reason": data.get("stop_reason", ""), "provider": self.config.name, "model": model_id, "usage": data.get("usage", {})}
            else:
                body = {"inputText": messages[-1].get("content", "") if messages else ""}
                resp = client.invoke_model(modelId=model_id, body=json.dumps(body), contentType="application/json")
                data = json.loads(resp["body"].read())
                self._mark_success()
                return {"text": str(data), "tool_calls": [], "stop_reason": "end_turn", "provider": self.config.name, "model": model_id, "usage": {}}

        except Exception as e:
            self._mark_error(str(e))
            raise ProviderError(str(e), self.config.name)

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None):
        client = self._get_boto_client()
        if not client:
            raise ProviderError("boto3_unavailable", self.config.name)

        model = self.get_model(tier, model_override)
        model_id = self.BEDROCK_MODELS.get(model, model)

        try:
            if "anthropic" in model_id:
                body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": max_tokens, "messages": messages}
                if system:
                    body["system"] = system
                if tools:
                    body["tools"] = [t.to_anthropic_schema() for t in tools]

                resp = client.invoke_model_with_response_stream(modelId=model_id, body=json.dumps(body), contentType="application/json")
                _stream_usage: dict[str, int] = {}
                for event in resp.get("body", []):
                    chunk = json.loads(event.get("chunk", {}).get("bytes", b"{}"))
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield {"type": "text", "text": delta["text"], "provider": self.config.name, "model": model_id}
                    elif chunk.get("type") == "message_delta":
                        _stream_usage["output_tokens"] = chunk.get("usage", {}).get("output_tokens", 0)
                    elif chunk.get("type") == "message_start":
                        _stream_usage.update(chunk.get("message", {}).get("usage", {}))
                    elif chunk.get("type") == "message_stop":
                        yield {"type": "done", "provider": self.config.name, "model": model_id, "usage": _stream_usage}
                self._mark_success()
        except Exception as e:
            self._mark_error(str(e))
            raise ProviderError(str(e), self.config.name)


# ═══════════════════════════════════════════════════════════════════════════════
# OPENROUTER ADAPTER (unified gateway — all models via OpenAI-compatible API)
# ═══════════════════════════════════════════════════════════════════════════════

class OpenRouterAdapter(OpenAIAdapter):
    """OpenRouter — one API key for all LLM providers (Anthropic, OpenAI, Google, etc.)."""

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://omnios.ai",
            "X-Title": "Omni OS",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

class ModelRouter:
    """Routes LLM requests with automatic failover. OpenRouter → Anthropic → OpenAI → Google."""

    def __init__(self):
        self.adapters: list[ProviderAdapter] = []
        adapter_map = {
            "openrouter": OpenRouterAdapter,
            "anthropic": AnthropicAdapter,
            "bedrock": BedrockAdapter,
            "openai": OpenAIAdapter,
            "google": GoogleAdapter,
        }
        for pc in settings.providers:
            cls = adapter_map.get(pc.name)
            if cls and pc.enabled:
                self.adapters.append(cls(pc))
                logger.info(f"Provider registered: {pc.name} ({pc.default_model})")
        if not self.adapters:
            logger.warning("No LLM providers configured!")

    async def complete(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None) -> dict:
        available = [a for a in self.adapters if a.is_available]
        if not available:
            raise AllProvidersFailedError([ProviderError("all_in_cooldown", a.config.name) for a in self.adapters])
        errors = []
        for adapter in available:
            try:
                result = await adapter.complete(messages, system, tools, tier, max_tokens, model_override)
                logger.info(f"Completed via {adapter.config.name} ({result.get('model')})")
                return result
            except ProviderError as e:
                errors.append(e)
                logger.warning(f"Failover: {adapter.config.name} → next")
        raise AllProvidersFailedError(errors)

    async def complete_stream(self, messages, system="", tools=None, tier=Tier.STANDARD, max_tokens=4096, model_override=None) -> AsyncGenerator[dict, None]:
        available = [a for a in self.adapters if a.is_available]
        if not available:
            raise AllProvidersFailedError([ProviderError("all_in_cooldown", a.config.name) for a in self.adapters])
        errors = []
        for adapter in available:
            try:
                async for chunk in adapter.complete_stream(messages, system, tools, tier, max_tokens, model_override):
                    yield chunk
                return
            except ProviderError as e:
                errors.append(e)
                logger.warning(f"Stream failover: {adapter.config.name} → next")
        raise AllProvidersFailedError(errors)

    def status(self) -> list[dict]:
        return [a.status() for a in self.adapters]


router = ModelRouter()
