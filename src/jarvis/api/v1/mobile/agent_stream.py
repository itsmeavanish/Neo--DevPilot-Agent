"""
Streaming agentic AI endpoint for mobile.

Exposes the ReAct agent loop via Server-Sent Events with typed events
for real-time tool-calling feedback on the mobile app.

Automatically detects complex tasks and routes them through the multi-model
pipeline (understand → plan → implement) for better results.
"""

import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .models import AgentStreamRequest
from jarvis.core.logging import get_logger

router = APIRouter()
logger = get_logger("jarvis.api.mobile.agent_stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


@router.post("/project/ai/agent-stream")
async def agent_stream(request: AgentStreamRequest):
    """
    Agentic AI with tool calling, streamed via SSE.

    Event types:
      - session: session_id assigned
      - thinking: agent is reasoning
      - tool_call: agent wants to use a tool
      - tool_result: tool execution result
      - token: streaming text chunk (final answer)
      - done: final assembled response
      - error: error occurred
    """

    async def event_generator() -> AsyncIterator[str]:
        from jarvis.chat.history import get_or_create_session, get_session_history, add_messages
        from jarvis.llm.ai_service import get_streaming_llm_client
        from jarvis.llm.router import get_model_router
        from jarvis.agent.react_loop import ReactAgentLoop
        from jarvis.agent.pipeline import PipelineOrchestrator, should_use_pipeline
        from jarvis.tools.registry import tool_registry

        try:
            sid = get_or_create_session(request.session_id)
            yield _sse({"type": "session", "session_id": sid})

            history = get_session_history(sid, limit=20) if request.session_id else []

            router = get_model_router()
            route = router.route(request.message, has_code_context=False)

            llm = await get_streaming_llm_client(
                preferred_provider="auto",
                model=route.model,
            )
            if not llm:
                yield _sse({"type": "error", "content": "No AI provider available. Configure FreeLLM or Ollama in Settings."})
                yield "data: [DONE]\n\n"
                return

            context = {}
            if request.pairing_code:
                context["pairing_code"] = request.pairing_code
            if request.workspace_root:
                context["workspace_root"] = request.workspace_root

            # Gather full workspace context (file tree + metadata)
            if request.workspace_root:
                from jarvis.tools.builtin.workspace_context import (
                    gather_workspace_context,
                    format_context_for_prompt,
                )
                ws_ctx = await gather_workspace_context(
                    request.workspace_root,
                    pairing_code=request.pairing_code,
                )
                if ws_ctx and not ws_ctx.get("error"):
                    context["folder_context"] = format_context_for_prompt(ws_ctx)

            use_pipeline = should_use_pipeline(request.message)

            if use_pipeline:
                # Multi-model pipeline: understand → plan → implement
                yield _sse({"type": "pipeline_start", "content": "Using multi-model pipeline: Understand → Plan → Implement"})

                pipeline = PipelineOrchestrator(
                    llm_client=llm,
                    registry=tool_registry,
                    max_steps=request.max_steps,
                )

                final_answer = ""
                async for step in pipeline.run(
                    request.message,
                    history=history,
                    context=context,
                ):
                    if step.type == "phase_start":
                        yield _sse({"type": "phase_start", "phase": step.phase, "content": step.content})
                    elif step.type == "phase_result":
                        yield _sse({"type": "phase_result", "phase": step.phase, "content": step.content, "model": step.model_used})
                    elif step.type == "thinking":
                        yield _sse({"type": "thinking", "content": step.content, "phase": step.phase})
                    elif step.type == "tool_call":
                        yield _sse({"type": "tool_call", "tool": step.tool_name, "args": step.tool_args, "phase": step.phase})
                    elif step.type == "tool_result":
                        result_preview = step.tool_result
                        if isinstance(result_preview, dict):
                            output = result_preview.get("output", "")
                            if isinstance(output, str) and len(output) > 2000:
                                result_preview = {**result_preview, "output": output[:2000] + "... (truncated)"}
                        yield _sse({"type": "tool_result", "tool": step.tool_name, "result": result_preview, "duration_ms": step.duration_ms, "phase": step.phase})
                    elif step.type == "final_answer":
                        final_answer = step.content
                        yield _sse({"type": "token", "content": step.content})
                    elif step.type == "error":
                        yield _sse({"type": "error", "content": step.content, "phase": step.phase})

            else:
                # Simple agent loop for straightforward queries
                agent = ReactAgentLoop(
                    llm_client=llm,
                    registry=tool_registry,
                    max_steps=request.max_steps,
                )

                final_answer = ""
                async for step in agent.run(request.message, history=history, context=context):
                    if step.type == "thinking":
                        yield _sse({"type": "thinking", "content": step.content, "step": step.step_number})
                    elif step.type == "tool_call":
                        yield _sse({
                            "type": "tool_call",
                            "tool": step.tool_name,
                            "args": step.tool_args,
                            "step": step.step_number,
                        })
                    elif step.type == "tool_result":
                        result_preview = step.tool_result
                        if isinstance(result_preview, dict):
                            output = result_preview.get("output", "")
                            if isinstance(output, str) and len(output) > 2000:
                                result_preview = {**result_preview, "output": output[:2000] + "... (truncated)"}
                        yield _sse({
                            "type": "tool_result",
                            "tool": step.tool_name,
                            "result": result_preview,
                            "step": step.step_number,
                            "duration_ms": step.duration_ms,
                        })
                    elif step.type == "final_answer":
                        final_answer = step.content
                        yield _sse({"type": "token", "content": step.content})
                    elif step.type == "error":
                        yield _sse({"type": "error", "content": step.content})

            if final_answer:
                add_messages(sid, [
                    {"role": "user", "content": request.message},
                    {"role": "assistant", "content": final_answer},
                ])

            yield _sse({"type": "done", "content": final_answer})
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("Agent stream error")
            yield _sse({"type": "error", "content": str(e)})
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
