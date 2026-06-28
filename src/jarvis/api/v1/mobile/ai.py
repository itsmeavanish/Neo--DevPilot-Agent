import json
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from .models import (
    AIProvidersResponse, SetProviderRequest, AIAskRequest, AIAskStreamRequest,
    AIResponse, AIKeysRequest, CopilotModelRequest, CopilotModelsResponse,
    OllamaConfigRequest, IDEAgentActionRequest, IDEAgentActionResponse,
    CopilotEditRequest, CopilotEditResponse, CommandRequest, CommandResponse,
    AIProviderStatus
)
from .utils import run_command, detect_language, generate_diff
from jarvis.runtime_llm import (
    DEFAULT_OLLAMA_MODEL, get_effective_ai_provider, get_effective_ollama_host,
    get_effective_ollama_model, get_runtime_llm, set_runtime_ai_provider, set_runtime_ollama
)
from jarvis.auth.github_token_store import get_stored_github_token

router = APIRouter()

def _current_provider() -> str:
    return get_effective_ai_provider() or _current_ai_provider

_current_ai_provider = "auto"

async def _check_ollama_available() -> tuple[bool, str]:
    try:
        from jarvis.llm.providers.ollama import OllamaClient
        host = get_effective_ollama_host()
        model = get_effective_ollama_model()
        client = OllamaClient(host=host, model=model)
        if not await client.is_available():
            return False, "Ollama not running. Start with: ollama serve"
        models = await client.list_models()
        names = {m.split(":")[0] for m in models}
        base = model.split(":")[0]
        if models and base not in names and not any(m.startswith(model) for m in models):
            return False, f"Model '{model}' not pulled. Run: ollama pull {model}"
        return True, f"Ollama OK — model: {model}"
    except Exception as e:
        return False, f"Ollama error: {str(e)}"

async def _check_copilot_available() -> tuple[bool, str]:
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        cli_provider = get_copilot_cli()
        cli_available, cli_message = await cli_provider.check_available()
        if cli_available:
            return True, f"CLI Copilot: {cli_message}"
        return False, cli_message or "Run `gh auth login` or use FreeLLM/Ollama."
    except Exception as e:
        return False, f"Copilot error: {str(e)}"

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
        return False, "FreeLLM API key invalid or expired"
    except Exception as e:
        return False, f"FreeLLM error: {str(e)}"

@router.get("/project/ai/providers", response_model=AIProvidersResponse)
async def get_ai_providers():
    ollama_available, ollama_message = await _check_ollama_available()
    copilot_available, copilot_message = await _check_copilot_available()
    freellm_available, freellm_message = await _check_freellm_available()

    providers = {
        "ollama": AIProviderStatus(available=ollama_available, message=ollama_message, selected=_current_provider() in ("ollama", "auto")),
        "copilot": AIProviderStatus(available=copilot_available, message=copilot_message, selected=_current_provider() in ("copilot", "auto")),
        "freellm": AIProviderStatus(available=freellm_available, message=freellm_message, selected=_current_provider() in ("freellm", "auto")),
        "cursor": AIProviderStatus(available=False, message="Cursor AI (coming soon)", selected=_current_ai_provider == "cursor")
    }
    return AIProvidersResponse(current=_current_provider(), providers=providers)

@router.post("/project/ai/set-provider")
async def set_ai_provider(request: SetProviderRequest):
    global _current_ai_provider
    valid_providers = ["auto", "ollama", "copilot", "freellm", "cursor"]
    if request.provider not in valid_providers:
        return {"success": False, "provider": request.provider, "message": f"Invalid provider. Choose from: {valid_providers}"}
    if request.provider == "auto":
        _current_ai_provider = "auto"
        set_runtime_ai_provider("auto")
        return {"success": True, "provider": "auto", "message": "Auto mode: tries GitHub/FreeLLM first, then Ollama."}

    checks = {"ollama": _check_ollama_available, "copilot": _check_copilot_available, "freellm": _check_freellm_available}
    if request.provider in checks:
        ok, msg = await checks[request.provider]()
        if not ok:
            return {"success": False, "provider": request.provider, "message": msg}

    _current_ai_provider = request.provider
    set_runtime_ai_provider(request.provider)
    return {"success": True, "provider": request.provider, "message": f"AI provider set to {request.provider}"}

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
    return {"success": True, "message": "AI configuration updated.", "freellm_configured": bool(runtime.get("freellm_api_key"))}

@router.get("/copilot/models", response_model=CopilotModelsResponse)
async def get_copilot_models():
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()
        return CopilotModelsResponse(current=provider.get_current_model(), models=provider.get_available_models())
    except Exception as e:
        return CopilotModelsResponse(current="gpt-5.2-codex", models={"Error": [f"Failed: {str(e)}"]})

@router.post("/copilot/models/set")
async def set_copilot_model(request: CopilotModelRequest):
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()
        provider.set_model(request.model)
        return {"success": True, "model": request.model, "message": f"Copilot model set to {request.model}"}
    except Exception as e:
        return {"success": False, "message": f"Failed: {str(e)}"}

@router.get("/copilot/status")
async def get_copilot_status():
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()
        token = get_stored_github_token()
        if token:
            from jarvis.llm.providers.copilot_api import get_copilot_api
            api = get_copilot_api()
            api.set_token(token)
            api_ok, api_msg = await api.check_available()
            return {
                "authentication": {"status": "authenticated" if api_ok else "token_invalid", "message": api_msg},
                "copilot": {"status": "available" if api_ok else "unavailable", "message": "Copilot API via Settings token"},
                "model": {"current": provider.get_current_model(), "available_count": len([m for models in provider.get_available_models().values() for m in models])}
            }
        auth_ok, auth_message = await provider.check_github_auth()
        copilot_ok, copilot_message = await provider.check_copilot_access()
        return {
            "authentication": {"status": "authenticated" if auth_ok else "not_authenticated", "message": auth_message},
            "copilot": {"status": "available" if copilot_ok else "unavailable", "message": copilot_message},
            "model": {"current": provider.get_current_model(), "available_count": len([model for models in provider.get_available_models().values() for model in models])}
        }
    except Exception as e:
        return {"authentication": {"status": "error", "message": str(e)}, "copilot": {"status": "error", "message": str(e)}, "model": {"current": "unknown", "available_count": 0}}

@router.post("/project/ai/ask", response_model=AIResponse)
async def ask_ai(request: AIAskRequest):
    from jarvis.llm.ai_service import generate_chat
    from jarvis.chat.history import get_or_create_session, get_session_history, add_messages
    from jarvis.tools.builtin.workspace_context import gather_workspace_context, format_context_for_prompt

    system_prompt = "You are a helpful AI coding assistant. Provide clear, concise answers."
    if request.file_path:
        system_prompt += f" The user is editing: {request.file_path}."

    # Gather workspace folder context for full-project awareness
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

    status, text, _tried = await generate_chat(prompt, system=system_prompt, code_context=request.code_context, preferred_provider=_current_provider())

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

    # Gather workspace folder context
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
                preferred_provider=_current_provider(),
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

@router.get("/project/ai/ollama-config")
async def get_ollama_config():
    return {"host": get_effective_ollama_host(), "model": get_effective_ollama_model(), "runtime": get_runtime_llm(), "default_small_model": DEFAULT_OLLAMA_MODEL}

@router.post("/project/ai/ollama-config")
async def post_ollama_config(body: OllamaConfigRequest):
    model = (body.model or get_effective_ollama_model()).strip()
    host = (body.host or get_effective_ollama_host()).strip()
    set_runtime_ollama(host=host, model=model)
    pull_msg = ""
    if body.pull and model:
        result = await run_command(f"ollama pull {model}", timeout=600)
        pull_msg = f" Pulled {model}." if result.status == "success" else f" Pull failed: {result.stderr or result.message}"
    ok, msg = await _check_ollama_available()
    return {"success": ok, "host": host, "model": model, "message": (msg or "Ollama configured.") + pull_msg}

@router.post("/project/ai/agent-action", response_model=IDEAgentActionResponse)
async def ide_agent_action(body: IDEAgentActionRequest):
    from jarvis.api.ide_agent_actions import run_agent_action
    result = await run_agent_action(body.intent.strip(), pairing_code=body.pairing_code, workspace_root=body.workspace_root)
    return IDEAgentActionResponse(**result)

@router.post("/copilot/run", response_model=CommandResponse)
async def run_copilot(request: CommandRequest):
    cmd = f'gh copilot suggest "{request.command}"'
    return await run_command(cmd)

@router.post("/copilot/edit", response_model=CopilotEditResponse)
async def copilot_edit(request: CopilotEditRequest):
    file_path = request.file_path
    if not os.path.exists(file_path):
        return CopilotEditResponse(success=False, original_content="", suggested_content="", diff="", message=f"File not found: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            original_content = f.read()
    except Exception as e:
        return CopilotEditResponse(success=False, original_content="", suggested_content="", diff="", message=f"Failed to read file: {e}")
    language = detect_language(file_path)
    from jarvis.llm.ai_service import generate_chat
    status, response, _ = await generate_chat(request.instruction, system="You are a code editor. Return ONLY the complete modified file content. No markdown fences, no explanations.", code_context=original_content, preferred_provider=_current_provider())
    suggested_content = ""
    if status == "success":
        suggested_content = response.strip()
        if suggested_content.startswith("```"):
            import re
            blocks = re.findall(r'```(?:\w+)?\n?(.*?)```', suggested_content, re.DOTALL)
            if blocks: suggested_content = blocks[0].strip()
    else:
        return CopilotEditResponse(success=False, original_content=original_content, suggested_content="", diff="", message=response or "AI unavailable")
    if not suggested_content:
        return CopilotEditResponse(success=False, original_content=original_content, suggested_content="", diff="", message="No suggestions")
    diff = generate_diff(original_content, suggested_content, file_path)
    applied = False
    if request.apply_changes:
        try:
            with open(f"{file_path}.backup", 'w', encoding='utf-8') as f: f.write(original_content)
            with open(file_path, 'w', encoding='utf-8') as f: f.write(suggested_content)
            applied = True
        except Exception as e:
            return CopilotEditResponse(success=False, original_content=original_content, suggested_content=suggested_content, diff=diff, message=f"Failed to apply: {e}")
    return CopilotEditResponse(success=True, original_content=original_content, suggested_content=suggested_content, diff=diff, message="Changes suggested" + (" and applied" if applied else " - review and apply"), applied=applied)
