import json
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from .models import (
    AIProvidersResponse, SetProviderRequest, AIAskRequest, AIAskStreamRequest,
    AIResponse, AIKeysRequest,
    IDEAgentActionRequest, IDEAgentActionResponse,
    AIProviderStatus
)
from .utils import run_command, detect_language, generate_diff
from jarvis.runtime_llm import get_runtime_llm

router = APIRouter()


async def _check_freellm_available() -> tuple[bool, str]:
    from jarvis.config import get_settings
    settings = get_settings()
    if not getattr(settings, "freellm_api_key", None):
        return False, "FreeLLM API key not configured"
    try:
        from jarvis.llm.providers.freellm import FreeLLMClient
        client = FreeLLMClient(api_key=settings.freellm_api_key, base_url=getattr(settings, "freellm_api_url", "http://localhost:3001/v1"))
        if await client.is_available():
            return True, "FreeLLM API configured"
        return False, "FreeLLM API key invalid or server unreachable"
    except Exception as e:
        return False, f"FreeLLM error: {str(e)}"

@router.get("/project/ai/providers", response_model=AIProvidersResponse)
async def get_ai_providers():
    freellm_available, freellm_message = await _check_freellm_available()
    providers = {
        "freellm": AIProviderStatus(available=freellm_available, message=freellm_message, selected=True),
    }
    return AIProvidersResponse(current="freellm", providers=providers)

@router.post("/project/ai/set-provider")
async def set_ai_provider(request: SetProviderRequest):
    if request.provider not in ("freellm", "auto"):
        return {"success": False, "provider": request.provider, "message": "Only FreeLLM provider is supported"}
    return {"success": True, "provider": "freellm", "message": "AI provider set to freellm"}

@router.post("/project/ai/keys")
async def save_ai_keys(body: AIKeysRequest):
    from jarvis.runtime_llm import get_runtime_llm, _save
    from jarvis.config import get_settings
    runtime = get_runtime_llm()
    if body.freellm_api_key is not None: runtime["freellm_api_key"] = body.freellm_api_key.strip()
    if body.freellm_api_url is not None: runtime["freellm_api_url"] = body.freellm_api_url.strip()
    if body.freellm_model is not None: runtime["freellm_model"] = body.freellm_model.strip()
    _save(runtime)
    get_settings.cache_clear()
    return {"success": True, "message": "FreeLLM configuration updated.", "freellm_configured": bool(runtime.get("freellm_api_key"))}

@router.post("/project/ai/ask", response_model=AIResponse)
async def ask_ai(request: AIAskRequest):
    from jarvis.llm.ai_service import generate_chat
    from jarvis.chat.history import get_or_create_session, get_session_history, add_messages
    from jarvis.tools.builtin.workspace_context import gather_workspace_context, format_context_for_prompt

    system_prompt = "You are a helpful AI coding assistant. Provide clear, concise answers."
    if request.file_path:
        system_prompt += f" The user is editing: {request.file_path}."

    if request.workspace_root:
        ws_ctx = await gather_workspace_context(request.workspace_root, pairing_code=request.pairing_code)
        folder_str = format_context_for_prompt(ws_ctx)
        if folder_str:
            system_prompt += f"\n\n{folder_str}\n\nUse this project structure to give informed answers. Reference specific files when relevant."

    sid = get_or_create_session(request.session_id)
    history = get_session_history(sid, limit=20) if request.session_id else []

    prompt = request.prompt
    if history:
        history_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-10:])
        prompt = f"Previous conversation:\n{history_text}\n\nUser: {request.prompt}"

    status, text, _tried = await generate_chat(prompt, system=system_prompt, code_context=request.code_context)

    if status == "success":
        add_messages(sid, [
            {"role": "user", "content": request.prompt},
            {"role": "assistant", "content": text},
        ])

    return AIResponse(
        status="success" if status == "success" else "error",
        response=text if status == "success" else "",
        error=text if status != "success" else None,
        session_id=sid,
    )


@router.post("/project/ai/ask-stream")
async def ask_ai_stream(request: AIAskStreamRequest):
    """Stream AI response via Server-Sent Events."""
    from jarvis.llm.ai_service import generate_chat_stream
    from jarvis.chat.history import get_or_create_session, get_session_history, add_messages
    from jarvis.tools.builtin.workspace_context import gather_workspace_context, format_context_for_prompt

    sid = get_or_create_session(request.session_id)
    history = get_session_history(sid, limit=20) if request.session_id else []

    system_prompt = "You are a helpful AI coding assistant. Provide clear, concise answers."
    if request.file_path:
        system_prompt += f" The user is editing: {request.file_path}."

    if request.workspace_root:
        ws_ctx = await gather_workspace_context(request.workspace_root, pairing_code=request.pairing_code)
        folder_str = format_context_for_prompt(ws_ctx)
        if folder_str:
            system_prompt += f"\n\n{folder_str}\n\nUse this project structure to give informed answers. Reference specific files when relevant."

    messages = [{"role": m["role"], "content": m["content"]} for m in history[-10:]] if history else None

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

        full_text = []
        try:
            async for chunk in generate_chat_stream(
                request.prompt,
                system=system_prompt,
                code_context=request.code_context,
                messages=messages,
            ):
                full_text.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            response_text = "".join(full_text)
            add_messages(sid, [
                {"role": "user", "content": request.prompt},
                {"role": "assistant", "content": response_text},
            ])
            yield f"data: {json.dumps({'type': 'done', 'content': response_text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/project/ai/sessions")
async def list_ai_sessions():
    """List chat sessions."""
    from jarvis.chat.history import list_sessions
    return {"sessions": list_sessions(limit=50)}


@router.get("/project/ai/sessions/{session_id}")
async def get_ai_session(session_id: str):
    """Get messages for a chat session."""
    from jarvis.chat.history import get_session_history
    messages = get_session_history(session_id, limit=100)
    return {"session_id": session_id, "messages": messages}


@router.delete("/project/ai/sessions/{session_id}")
async def delete_ai_session(session_id: str):
    """Delete a chat session."""
    from jarvis.chat.history import delete_session
    delete_session(session_id)
    return {"success": True, "message": f"Session {session_id} deleted"}

@router.post("/project/ai/agent-action", response_model=IDEAgentActionResponse)
async def ide_agent_action(body: IDEAgentActionRequest):
    from jarvis.api.ide_agent_actions import run_agent_action
    result = await run_agent_action(body.intent.strip(), pairing_code=body.pairing_code, workspace_root=body.workspace_root)
    return IDEAgentActionResponse(**result)
