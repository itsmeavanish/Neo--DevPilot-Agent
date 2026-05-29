"""
Chat API endpoint – multi-turn conversational AI with session history.

Adds:
  POST /api/v1/agent/chat            – stateless turn (client sends history)
  POST /api/v1/agent/chat/stream     – SSE streaming turn
  POST /api/v1/agent/review          – AI code-review
"""

import json
import asyncio
import re
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis.api.deps import get_agent_async
from jarvis.agent import AgentLoop
from jarvis.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.chat")

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# In-process session store
# ─────────────────────────────────────────────────────────────────────────────

# Maps session_id → list of {"role": ..., "content": ...} dicts
_sessions: dict[str, list[dict[str, str]]] = {}
_MAX_HISTORY = 40  # messages kept per session


def _get_or_create_session(session_id: str | None) -> tuple[str, list[dict[str, str]]]:
    sid = session_id or str(uuid.uuid4())[:12]
    if sid not in _sessions:
        _sessions[sid] = []
    return sid, _sessions[sid]


JARVIS_SYSTEM_PROMPT = """You are JARVIS, an elite autonomous developer assistant built on \
Neo–DevPilot-Agent. You help developers write, review, debug, refactor, and ship code faster.

Your personality: concise, expert, no unnecessary fluff. You speak like a senior engineer.

You can:
- Answer programming questions with working code examples
- Explain errors and suggest fixes
- Review code and spot bugs, security issues, anti-patterns
- Help design software architecture
- Execute actions via the agent loop when the user wants something done

When you include code, always wrap it in ``` with the language identifier."""


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="The new user message")
    history: list[ChatMessage] = Field(default_factory=list, description="Prior turns")
    session_id: str | None = Field(default=None, description="Session ID for server-side history")
    system_prompt: str | None = Field(default=None, description="Override system prompt")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "How do I reverse a string in Python?",
                    "history": [],
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    session_id: str
    response: str
    error: str | None = None


class CodeReviewRequest(BaseModel):
    code: str = Field(..., description="Source code to review")
    language: str = Field(default="python", description="Programming language")
    file_path: str | None = Field(default=None, description="Optional file path for context")


class CodeIssue(BaseModel):
    severity: str = Field(..., description="'critical', 'warning', or 'info'")
    line: int | None = None
    message: str
    suggestion: str | None = None


class CodeReviewResponse(BaseModel):
    summary: str
    issues: list[CodeIssue]
    score: int = Field(description="Code quality score 0-100")
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# LLM helper
# ─────────────────────────────────────────────────────────────────────────────


async def _get_llm_client():
    """Build an LLM client from active settings, trying providers in order."""
    settings = get_settings()

    # 1. OpenAI (if key set)
    if settings.openai_api_key:
        from jarvis.llm.providers.openai import OpenAIClient
        client = OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)
        if await client.is_available():
            return client

    # 2. Ollama
    if settings.ollama_host:
        try:
            from jarvis.llm.providers.ollama import OllamaClient
            client = OllamaClient(host=settings.ollama_host, model=settings.ollama_model)
            if await client.is_available():
                return client
        except Exception:
            pass

    # 3. GitHub Copilot CLI
    try:
        from jarvis.llm.providers.copilot import CopilotClient
        client = CopilotClient()
        if await client.is_available():
            return client
    except Exception:
        pass

    return None


def _build_messages(
    history: list[ChatMessage],
    user_message: str,
) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    for h in history[-_MAX_HISTORY:]:
        msgs.append({"role": h.role, "content": h.content})
    msgs.append({"role": "user", "content": user_message})
    return msgs


# ─────────────────────────────────────────────────────────────────────────────
# Chat – single turn (non-streaming)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse, summary="Multi-turn chat with JARVIS")
async def chat(request: ChatRequest):
    """
    Send a message to JARVIS and receive a reply.

    - Maintains conversation history per ``session_id`` on the server.
    - Client may also pass ``history`` directly (server-side history takes precedence).
    - Falls back through OpenAI → Ollama → Copilot CLI automatically.
    """
    sid, server_history = _get_or_create_session(request.session_id)

    # Merge client-provided history with server-side history
    # (if session is new, use client-provided history as seed)
    if not server_history and request.history:
        server_history.extend([h.model_dump() for h in request.history])

    msgs = _build_messages(
        [ChatMessage(**m) for m in server_history],
        request.message,
    )

    from jarvis.llm.ai_service import generate_chat
    from jarvis.runtime_llm import get_effective_ai_provider

    system = request.system_prompt or JARVIS_SYSTEM_PROMPT
    # Flatten recent history into prompt for providers that use single-shot generate
    history_blob = ""
    for m in msgs[:-1]:
        history_blob += f"{m['role'].upper()}: {m['content']}\n\n"
    full_user = f"{history_blob}USER: {request.message}" if history_blob else request.message

    status, reply, _ = await generate_chat(
        full_user,
        system=system,
        preferred_provider=get_effective_ai_provider() or "auto",
    )

    if status != "success":
        return ChatResponse(session_id=sid, response="", error=reply)

    server_history.append({"role": "user", "content": request.message})
    server_history.append({"role": "assistant", "content": reply})
    if len(server_history) > _MAX_HISTORY:
        _sessions[sid] = server_history[-_MAX_HISTORY:]

    return ChatResponse(session_id=sid, response=reply)


# ─────────────────────────────────────────────────────────────────────────────
# Chat – SSE streaming
# ─────────────────────────────────────────────────────────────────────────────


async def _sse_generator(request: ChatRequest) -> AsyncIterator[str]:
    """Yield Server-Sent Events for streaming chat."""
    sid, server_history = _get_or_create_session(request.session_id)

    if not server_history and request.history:
        server_history.extend([h.model_dump() for h in request.history])

    msgs = _build_messages(
        [ChatMessage(**m) for m in server_history],
        request.message,
    )

    # Send session_id first
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    llm = await _get_llm_client()
    if llm is None:
        error_msg = (
            "No LLM provider available. "
            "Start Ollama ('ollama serve') or set JARVIS_OPENAI_API_KEY."
        )
        yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        yield "data: [DONE]\n\n"
        return

    system = request.system_prompt or JARVIS_SYSTEM_PROMPT
    full_reply: list[str] = []

    try:
        async for chunk in llm.chat_stream(messages=msgs, system=system):
            full_reply.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0)  # yield control

        assembled = "".join(full_reply)
        server_history.append({"role": "user", "content": request.message})
        server_history.append({"role": "assistant", "content": assembled})
        if len(server_history) > _MAX_HISTORY:
            _sessions[sid] = server_history[-_MAX_HISTORY:]

        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Streaming chat error")
        yield f"data: {json.dumps({'type': 'error', 'content': 'An internal error occurred. Please try again.'})}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/chat/stream", summary="Stream a chat reply via Server-Sent Events")
async def chat_stream(request: ChatRequest):
    """
    Like ``/chat`` but streams the reply token-by-token using SSE.

    Each event is a JSON object::

        {"type": "session", "session_id": "..."}   # first event
        {"type": "chunk",   "content": "Hello"}     # one or more
        {"type": "error",   "content": "..."}        # on failure
        data: [DONE]                                 # final sentinel
    """
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI Code Review
# ─────────────────────────────────────────────────────────────────────────────

_REVIEW_SYSTEM = """You are an expert code reviewer. Analyse the provided code and respond ONLY \
with a JSON object in this exact schema – no markdown, no explanation outside the JSON:

{
  "summary": "<one-sentence overview of code quality>",
  "issues": [
    {
      "severity": "critical|warning|info",
      "line": <integer or null>,
      "message": "<what the issue is>",
      "suggestion": "<how to fix it>"
    }
  ],
  "score": <integer 0-100>
}

Scoring guide: 90-100 excellent, 70-89 good, 50-69 fair, <50 poor."""


@router.post("/review", response_model=CodeReviewResponse, summary="AI code review")
async def review_code(request: CodeReviewRequest):
    """
    Submit code for an AI-powered review.

    Returns a structured report with a quality score, list of issues
    (critical / warning / info) and a one-line summary.
    """
    llm = await _get_llm_client()
    if llm is None:
        return CodeReviewResponse(
            summary="LLM unavailable",
            issues=[],
            score=0,
            error="No LLM provider configured.",
        )

    context = f"File: {request.file_path}\n" if request.file_path else ""
    user_msg = (
        f"{context}Language: {request.language}\n\n"
        f"```{request.language}\n{request.code}\n```"
    )

    try:
        raw = await llm.chat(
            messages=[{"role": "user", "content": user_msg}],
            system=_REVIEW_SYSTEM,
        )

        # Extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return CodeReviewResponse(
                summary="Could not parse review",
                issues=[],
                score=0,
                error=f"Unexpected LLM response: {raw[:200]}",
            )

        data = json.loads(json_match.group())
        issues = [
            CodeIssue(
                severity=i.get("severity", "info"),
                line=i.get("line"),
                message=i.get("message", ""),
                suggestion=i.get("suggestion"),
            )
            for i in data.get("issues", [])
        ]
        return CodeReviewResponse(
            summary=data.get("summary", ""),
            issues=issues,
            score=int(data.get("score", 50)),
        )

    except Exception as exc:
        logger.exception("Code review error")
        return CodeReviewResponse(
            summary="Review failed",
            issues=[],
            score=0,
            error="An internal error occurred while reviewing the code.",
        )


__all__ = ["router"]
