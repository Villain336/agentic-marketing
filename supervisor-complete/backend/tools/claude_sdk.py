"""
Omni OS — Claude Agent SDK Tools
Provides reliable code generation, code review, and agentic coding
capabilities to all agents via the Anthropic Claude API with tool_use.
"""
from __future__ import annotations
import json
import logging
from typing import Any

from tools.registry import ToolRegistry, _http_long

logger = logging.getLogger("omnios.tools.claude_sdk")


async def _claude_generate_code(
    language: str = "python",
    description: str = "",
    context: str = "",
    framework: str = "",
    style: str = "production",
) -> str:
    """Generate production-quality code using Claude's structured output."""
    from config import settings

    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        # Fallback: return a structured code template
        return json.dumps({
            "status": "generated",
            "language": language,
            "description": description,
            "code": f"# Auto-generated {language} code for: {description}\n# Framework: {framework or 'standard'}\n# TODO: Connect API key for Claude SDK to enable AI code generation\n\nraise NotImplementedError('Configure ANTHROPIC_API_KEY for AI code generation')",
            "tests": "",
            "notes": "Configure ANTHROPIC_API_KEY for full AI code generation",
        })

    # Determine if we use OpenRouter or direct Anthropic
    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://omnios.ai",
            "X-Title": "Omni OS",
        }
        url = f"{base_url}/v1/chat/completions"
    else:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{base_url}/v1/messages"

    system_prompt = f"""You are an expert {language} developer. Generate production-quality code.
Rules:
- Write clean, well-structured, idiomatic {language} code
- Include error handling and input validation
- Follow {framework + ' ' if framework else ''}best practices
- Style: {style}
- Include docstrings/comments only where logic is non-obvious
- Return ONLY the code, no explanations"""

    user_prompt = f"""Generate {language} code for: {description}"""
    if context:
        user_prompt += f"\n\nExisting context/codebase:\n{context}"
    if framework:
        user_prompt += f"\n\nFramework: {framework}"

    try:
        if is_openrouter:
            body = {
                "model": "anthropic/claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        else:
            body = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }

        resp = await _http_long.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        # Extract text from response
        if is_openrouter:
            code = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            code = "".join(
                blk["text"] for blk in data.get("content", []) if blk.get("type") == "text"
            )

        return json.dumps({
            "status": "generated",
            "language": language,
            "framework": framework,
            "code": code,
            "description": description,
        })

    except Exception as e:
        logger.error(f"Claude code generation failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def _claude_review_code(
    code: str = "",
    language: str = "python",
    focus: str = "security,performance,readability",
) -> str:
    """Review code using Claude for bugs, security issues, and improvements."""
    from config import settings

    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        return json.dumps({
            "status": "review_pending",
            "summary": "Code review requires ANTHROPIC_API_KEY",
            "issues": [],
        })

    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{base_url}/v1/chat/completions"
    else:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{base_url}/v1/messages"

    system_prompt = f"""You are an expert code reviewer. Review the {language} code below.
Focus areas: {focus}
Return a JSON object with:
- summary: brief overall assessment
- issues: array of {{severity: "critical"|"warning"|"info", line: number, description: string, fix: string}}
- score: 1-10 quality score
- improved_code: the fixed version of the code if issues found"""

    try:
        if is_openrouter:
            body = {
                "model": "anthropic/claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this code:\n```{language}\n{code}\n```"},
                ],
            }
        else:
            body = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": f"Review this code:\n```{language}\n{code}\n```"}],
            }

        resp = await _http_long.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        if is_openrouter:
            review = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            review = "".join(
                blk["text"] for blk in data.get("content", []) if blk.get("type") == "text"
            )

        return json.dumps({"status": "reviewed", "review": review})

    except Exception as e:
        logger.error(f"Claude code review failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def _claude_refactor_code(
    code: str = "",
    language: str = "python",
    goal: str = "improve readability and performance",
) -> str:
    """Refactor code using Claude for better quality."""
    from config import settings

    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        return json.dumps({
            "status": "refactor_pending",
            "note": "Configure ANTHROPIC_API_KEY for AI refactoring",
        })

    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/v1/chat/completions"
    else:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        url = f"{base_url}/v1/messages"

    system_prompt = f"""You are an expert {language} developer. Refactor the code to: {goal}.
Return ONLY the refactored code, no explanations. Preserve all functionality."""

    try:
        if is_openrouter:
            body = {
                "model": "anthropic/claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Refactor this code:\n```{language}\n{code}\n```"},
                ],
            }
        else:
            body = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": f"Refactor this code:\n```{language}\n{code}\n```"}],
            }

        resp = await _http_long.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        if is_openrouter:
            refactored = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            refactored = "".join(
                blk["text"] for blk in data.get("content", []) if blk.get("type") == "text"
            )

        return json.dumps({"status": "refactored", "language": language, "code": refactored, "goal": goal})

    except Exception as e:
        logger.error(f"Claude refactor failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})


async def _claude_explain_code(
    code: str = "",
    language: str = "python",
    audience: str = "developer",
) -> str:
    """Explain code using Claude — useful for documentation and onboarding."""
    from config import settings

    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        return json.dumps({"status": "pending", "note": "Configure ANTHROPIC_API_KEY"})

    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/v1/chat/completions"
    else:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        url = f"{base_url}/v1/messages"

    try:
        prompt = f"Explain this {language} code for a {audience}:\n```{language}\n{code}\n```"
        if is_openrouter:
            body = {"model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        else:
            body = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}

        resp = await _http_long.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        if is_openrouter:
            explanation = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            explanation = "".join(blk["text"] for blk in data.get("content", []) if blk.get("type") == "text")

        return json.dumps({"status": "explained", "explanation": explanation})

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


async def _claude_generate_tests(
    code: str = "",
    language: str = "python",
    framework: str = "pytest",
) -> str:
    """Generate comprehensive test suites using Claude."""
    from config import settings

    api_key = next(
        (p.api_key for p in settings.providers if p.name == "anthropic" and p.enabled),
        None,
    ) or next(
        (p.api_key for p in settings.providers if p.name == "openrouter" and p.enabled),
        None,
    )

    if not api_key:
        return json.dumps({"status": "pending", "note": "Configure ANTHROPIC_API_KEY"})

    is_openrouter = not any(p.name == "anthropic" and p.enabled for p in settings.providers)
    base_url = "https://openrouter.ai/api" if is_openrouter else "https://api.anthropic.com"

    headers = {}
    if is_openrouter:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/v1/chat/completions"
    else:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        url = f"{base_url}/v1/messages"

    system_prompt = f"""Generate comprehensive {framework} tests for the {language} code.
Include: unit tests, edge cases, error handling tests.
Return ONLY the test code, no explanations."""

    try:
        prompt = f"Generate tests for:\n```{language}\n{code}\n```"
        if is_openrouter:
            body = {"model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 8192, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]}
        else:
            body = {"model": "claude-sonnet-4-20250514", "max_tokens": 8192, "system": system_prompt, "messages": [{"role": "user", "content": prompt}]}

        resp = await _http_long.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        if is_openrouter:
            tests = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            tests = "".join(blk["text"] for blk in data.get("content", []) if blk.get("type") == "text")

        return json.dumps({"status": "generated", "framework": framework, "tests": tests})

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


def register_claude_sdk_tools(reg: ToolRegistry):
    """Register all Claude Agent SDK tools."""
    from models import ToolParameter

    reg.register(
        "claude_generate_code", "Generate production-quality code using Claude AI with structured output",
        [
            ToolParameter(name="language", type="string", description="Programming language (python, typescript, go, rust, etc.)", required=True),
            ToolParameter(name="description", type="string", description="What the code should do", required=True),
            ToolParameter(name="context", type="string", description="Existing code context or codebase snippets"),
            ToolParameter(name="framework", type="string", description="Framework to use (fastapi, nextjs, react, express, etc.)"),
            ToolParameter(name="style", type="string", description="Code style: production, prototype, minimal"),
        ],
        _claude_generate_code, category="ai", timeout=120,
    )

    reg.register(
        "claude_review_code", "Review code for bugs, security issues, and improvements using Claude AI",
        [
            ToolParameter(name="code", type="string", description="The code to review", required=True),
            ToolParameter(name="language", type="string", description="Programming language"),
            ToolParameter(name="focus", type="string", description="Focus areas: security, performance, readability, bugs"),
        ],
        _claude_review_code, category="ai", timeout=120,
    )

    reg.register(
        "claude_refactor_code", "Refactor code for better quality using Claude AI",
        [
            ToolParameter(name="code", type="string", description="The code to refactor", required=True),
            ToolParameter(name="language", type="string", description="Programming language"),
            ToolParameter(name="goal", type="string", description="Refactoring goal"),
        ],
        _claude_refactor_code, category="ai", timeout=120,
    )

    reg.register(
        "claude_explain_code", "Explain code using Claude AI for documentation and understanding",
        [
            ToolParameter(name="code", type="string", description="The code to explain", required=True),
            ToolParameter(name="language", type="string", description="Programming language"),
            ToolParameter(name="audience", type="string", description="Target audience: developer, beginner, executive"),
        ],
        _claude_explain_code, category="ai", timeout=60,
    )

    reg.register(
        "claude_generate_tests", "Generate comprehensive test suites using Claude AI",
        [
            ToolParameter(name="code", type="string", description="The code to generate tests for", required=True),
            ToolParameter(name="language", type="string", description="Programming language"),
            ToolParameter(name="framework", type="string", description="Test framework: pytest, jest, vitest, go-test"),
        ],
        _claude_generate_tests, category="ai", timeout=120,
    )
