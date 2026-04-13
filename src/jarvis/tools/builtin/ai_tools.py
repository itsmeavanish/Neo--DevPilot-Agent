"""
AI-powered tools for JARVIS.

Provides three higher-level tools backed by the active LLM:
  - code_review:      Review code and return structured findings.
  - generate_code:    Generate code from a natural-language description.
  - explain_command:  Explain what a shell command does before running it.
"""

import json
import re
from typing import ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel


async def _get_llm():
    """Return the first available LLM client (OpenAI → Ollama → Copilot)."""
    from jarvis.config import get_settings
    settings = get_settings()

    if settings.openai_api_key:
        try:
            from jarvis.llm.providers.openai import OpenAIClient
            client = OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)
            if await client.is_available():
                return client
        except Exception:
            pass

    if settings.ollama_host:
        try:
            from jarvis.llm.providers.ollama import OllamaClient
            client = OllamaClient(host=settings.ollama_host, model=settings.ollama_model)
            if await client.is_available():
                return client
        except Exception:
            pass

    try:
        from jarvis.llm.providers.copilot import CopilotClient
        client = CopilotClient()
        if await client.is_available():
            return client
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# code_review
# ─────────────────────────────────────────────────────────────────────────────

_REVIEW_SYSTEM = """You are a senior engineer performing a code review.
Respond ONLY with a JSON object – no extra text, no markdown:
{
  "summary": "<one sentence overall assessment>",
  "issues": [
    {"severity": "critical|warning|info", "line": <int or null>, "message": "...", "suggestion": "..."}
  ],
  "score": <0-100>
}"""


@tool_registry.register
class CodeReviewTool(BaseTool):
    """AI-powered code review that returns structured findings."""

    name: ClassVar[str] = "code_review"
    description: ClassVar[str] = (
        "Review a snippet of code using AI. Returns a quality score, list of issues "
        "(with severity critical/warning/info), and a one-line summary."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The source code to review",
            },
            "language": {
                "type": "string",
                "description": "Programming language (e.g. python, javascript, go)",
            },
            "file_path": {
                "type": "string",
                "description": "Optional file path for context",
            },
        },
        "required": ["code", "language"],
    }

    async def execute(self, params: dict) -> ToolResult:
        code = params["code"]
        language = params.get("language", "unknown")
        file_path = params.get("file_path", "")

        llm = await _get_llm()
        if llm is None:
            return ToolResult.failure("No LLM provider available for code review.")

        context = f"File: {file_path}\n" if file_path else ""
        user_msg = f"{context}Language: {language}\n\n```{language}\n{code}\n```"

        try:
            raw = await llm.chat(messages=[{"role": "user", "content": user_msg}], system=_REVIEW_SYSTEM)
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return ToolResult.failure(f"LLM returned no JSON: {raw[:200]}")

            data = json.loads(match.group())
            return ToolResult.success(data)

        except Exception as exc:
            return ToolResult.failure(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# generate_code
# ─────────────────────────────────────────────────────────────────────────────

_GENERATE_SYSTEM = """You are an expert software engineer.
Generate high-quality, production-ready code based on the user's description.
Return ONLY the code with no prose explanation.
If you include a code fence (```), make sure to close it properly."""


@tool_registry.register
class GenerateCodeTool(BaseTool):
    """Generate code from a natural-language description using AI."""

    name: ClassVar[str] = "generate_code"
    description: ClassVar[str] = (
        "Generate code from a description. Useful for scaffolding functions, classes, "
        "tests, or any code pattern described in plain English."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 120

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Natural-language description of the code to generate",
            },
            "language": {
                "type": "string",
                "description": "Target programming language",
            },
            "context": {
                "type": "string",
                "description": "Optional existing code context / file content",
            },
        },
        "required": ["description", "language"],
    }

    async def execute(self, params: dict) -> ToolResult:
        description = params["description"]
        language = params.get("language", "python")
        context = params.get("context", "")

        llm = await _get_llm()
        if llm is None:
            return ToolResult.failure("No LLM provider available for code generation.")

        user_msg = description
        if context:
            user_msg = (
                f"Existing code context:\n```{language}\n{context}\n```\n\n"
                f"Task: {description}"
            )

        try:
            raw = await llm.chat(messages=[{"role": "user", "content": user_msg}], system=_GENERATE_SYSTEM)

            # Strip outer markdown fence if present
            code_match = re.search(r"```(?:\w+)?\n?([\s\S]*?)```", raw)
            code = code_match.group(1).strip() if code_match else raw.strip()

            return ToolResult.success({"code": code, "language": language})

        except Exception as exc:
            return ToolResult.failure(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# explain_command
# ─────────────────────────────────────────────────────────────────────────────

_EXPLAIN_SYSTEM = """You are a shell expert. Given a shell command, explain clearly and concisely:
1. What the command does
2. Each flag / argument used
3. Any potential risks or side effects

Keep the explanation under 200 words."""


@tool_registry.register
class ExplainCommandTool(BaseTool):
    """Explain what a shell command does before executing it."""

    name: ClassVar[str] = "explain_command"
    description: ClassVar[str] = (
        "Explain a shell command in plain English including flag meanings and risks. "
        "Use this before running unfamiliar commands."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.LOW
    timeout: ClassVar[int] = 60

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to explain",
            },
        },
        "required": ["command"],
    }

    async def execute(self, params: dict) -> ToolResult:
        command = params["command"]

        llm = await _get_llm()
        if llm is None:
            return ToolResult.failure("No LLM provider available.")

        try:
            explanation = await llm.chat(
                messages=[{"role": "user", "content": f"Command: {command}"}],
                system=_EXPLAIN_SYSTEM,
            )
            return ToolResult.success({"command": command, "explanation": explanation})

        except Exception as exc:
            return ToolResult.failure(str(exc))


__all__ = ["CodeReviewTool", "GenerateCodeTool", "ExplainCommandTool"]
