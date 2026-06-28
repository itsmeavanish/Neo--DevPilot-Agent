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
# ─────────────────────────────────────────────────────────────────────────────
# Session Store
# ─────────────────────────────────────────────────────────────────────────────

from jarvis.chat.history import (
    get_or_create_session,
    get_session_history,
    add_messages,
    list_sessions,
    delete_session
)
_MAX_HISTORY = 40  # messages kept per session


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
    workspace_root: str | None = Field(default=None, description="Project workspace root for folder-aware context")
    pairing_code: str | None = Field(default=None, description="Pairing code for remote laptop access")

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

    # 1. FreeLLM (if key set)
    if getattr(settings, "freellm_api_key", None):
        from jarvis.llm.providers.freellm import FreeLLMClient
        client = FreeLLMClient(api_key=settings.freellm_api_key, base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"))
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
    sid = get_or_create_session(request.session_id)
    server_history = get_session_history(sid, limit=_MAX_HISTORY)

    # Merge client-provided history with server-side history
    # (if session is new, use client-provided history as seed)
    if not server_history and request.history:
        client_history = [h.model_dump() for h in request.history]
        server_history.extend(client_history)
        add_messages(sid, client_history)

    msgs = _build_messages(
        [ChatMessage(**m) for m in server_history],
        request.message,
    )

    from jarvis.llm.ai_service import generate_chat
    from jarvis.runtime_llm import get_effective_ai_provider

    system = request.system_prompt or JARVIS_SYSTEM_PROMPT

    # Inject workspace folder context for full-project awareness
    if request.workspace_root:
        from jarvis.tools.builtin.workspace_context import gather_workspace_context, format_context_for_prompt
        ws_ctx = await gather_workspace_context(request.workspace_root, pairing_code=request.pairing_code)
        folder_str = format_context_for_prompt(ws_ctx)
        if folder_str:
            system += f"\n\n{folder_str}\n\nUse this project structure to give informed, file-specific answers."

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

    add_messages(sid, [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": reply}
    ])

    return ChatResponse(session_id=sid, response=reply)


# ─────────────────────────────────────────────────────────────────────────────
# Chat – SSE streaming
# ─────────────────────────────────────────────────────────────────────────────


async def _sse_generator(request: ChatRequest) -> AsyncIterator[str]:
    """
    Yield Server-Sent Events for streaming chat.

    Routes through the ReAct agent loop so natural-language commands
    (e.g. "open my project in VS Code") are executed as actions,
    while regular questions are answered conversationally.
    """
    from jarvis.llm.ai_service import get_streaming_llm_client
    from jarvis.agent.react_loop import ReactAgentLoop
    from jarvis.tools.registry import tool_registry

    sid = get_or_create_session(request.session_id)
    server_history = get_session_history(sid, limit=_MAX_HISTORY)

    if not server_history and request.history:
        client_history = [h.model_dump() for h in request.history]
        server_history.extend(client_history)
        add_messages(sid, client_history)

    # Send session_id first
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    llm = await get_streaming_llm_client(preferred_provider="auto")
    if llm is None:
        error_msg = (
            "No LLM provider available. "
            "Configure FreeLLM or Ollama in Settings."
        )
        yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Build execution context
    context: dict[str, Any] = {}
    if request.workspace_root:
        context["workspace_root"] = request.workspace_root
    if request.pairing_code:
        context["pairing_code"] = request.pairing_code

    # Gather folder context for project awareness
    if request.workspace_root:
        from jarvis.tools.builtin.workspace_context import gather_workspace_context, format_context_for_prompt
        ws_ctx = await gather_workspace_context(request.workspace_root, pairing_code=request.pairing_code)
        folder_str = format_context_for_prompt(ws_ctx)
        if folder_str:
            context["folder_context"] = folder_str

    # Set pairing context so paired_* tools can access the pairing code
    from jarvis.execution_context import set_pairing_context, clear_pairing_context
    from jarvis.security.policy import Capability
    all_caps = [c.value for c in Capability]
    pairing_tokens = None
    if request.pairing_code:
        pairing_tokens = set_pairing_context(
            request.pairing_code,
            capabilities=all_caps,
            workspace_root=request.workspace_root,
        )

    # Use the ReAct agent loop — chat IS the command interface
    history = [{"role": m.role, "content": m.content} for m in
               [ChatMessage(**m) for m in server_history]]

    agent = ReactAgentLoop(
        llm_client=llm,
        registry=tool_registry,
        max_steps=8,
    )

    final_answer = ""
    try:
        async for step in agent.run(request.message, history=history[-10:], context=context):
            if step.type == "thinking":
                yield f"data: {json.dumps({'type': 'thinking', 'content': step.content})}\n\n"
            elif step.type == "tool_call":
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': step.tool_name, 'args': step.tool_args})}\n\n"
            elif step.type == "tool_result":
                result_preview = step.tool_result
                if isinstance(result_preview, dict):
                    output = result_preview.get("output", "")
                    if isinstance(output, str) and len(output) > 2000:
                        result_preview = {**result_preview, "output": output[:2000] + "... (truncated)"}
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': step.tool_name, 'result': result_preview}, default=str)}\n\n"
            elif step.type == "final_answer":
                final_answer = step.content
                yield f"data: {json.dumps({'type': 'chunk', 'content': step.content})}\n\n"
            elif step.type == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': step.content})}\n\n"

        if final_answer:
            add_messages(sid, [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": final_answer}
            ])

        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Streaming chat error")
        yield f"data: {json.dumps({'type': 'error', 'content': 'An internal error occurred. Please try again.'})}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        if pairing_tokens:
            clear_pairing_context(pairing_tokens)


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
# Chat History Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chat/history", summary="List chat sessions")
async def get_chat_history_sessions():
    """Returns a list of recent chat sessions."""
    try:
        return {"sessions": list_sessions()}
    except Exception as e:
        logger.exception("Failed to list chat sessions")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/history/{session_id}", summary="Get chat session history")
async def get_chat_history(session_id: str):
    """Returns the full message history for a specific session."""
    try:
        return {"session_id": session_id, "messages": get_session_history(session_id, limit=500)}
    except Exception as e:
        logger.exception("Failed to get chat history")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/history/{session_id}", summary="Delete chat session")
async def delete_chat_session(session_id: str):
    """Deletes a specific chat session."""
    try:
        delete_session(session_id)
        return {"success": True, "session_id": session_id}
    except Exception as e:
        logger.exception("Failed to delete chat session")
        raise HTTPException(status_code=500, detail=str(e))



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
