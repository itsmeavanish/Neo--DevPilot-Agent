"""
Streaming agentic AI endpoint for mobile.

Exposes the ReAct agent loop via Server-Sent Events with typed events
for real-time tool-calling feedback on the mobile app.

Automatically detects complex tasks and routes them through the multi-model
pipeline (understand → plan → implement) for better results.
"""

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from .models import AgentStreamRequest
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import (
    LLMConnectionError,
    LLMError,
    ToolExecutionError,
    ToolTimeoutError,
    AgentError,
)

router = APIRouter()
logger = get_logger("jarvis.api.mobile.agent_stream")

# Timeout for the entire agent loop (in seconds)
DEFAULT_AGENT_TIMEOUT = 120


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
      - done: final assembled response (includes usage stats)
      - error: error occurred
    """
    # Validate request
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.max_steps < 1 or request.max_steps > 30:
        raise HTTPException(status_code=400, detail="max_steps must be between 1 and 30")

    async def event_generator() -> AsyncIterator[str]:
        from jarvis.chat.history import get_or_create_session, get_session_history, add_messages
        from jarvis.llm.ai_service import get_streaming_llm_client
        from jarvis.llm.router import get_model_router
        from jarvis.agent.react_loop import ReactAgentLoop
        from jarvis.agent.pipeline import PipelineOrchestrator, should_use_pipeline
        from jarvis.tools.registry import tool_registry

        pairing_tokens = None
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            # Wrap the entire agent loop in a timeout
            async with asyncio.timeout(DEFAULT_AGENT_TIMEOUT):
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

                # Set pairing context so paired_* tools can access the pairing code
                from jarvis.execution_context import set_pairing_context, clear_pairing_context
                from jarvis.security.policy import Capability
                all_caps = [c.value for c in Capability]
                if request.pairing_code:
                    pairing_tokens = set_pairing_context(
                        request.pairing_code,
                        capabilities=all_caps,
                        workspace_root=request.workspace_root,
                    )

                # Gather full workspace context (file tree + metadata)
                if request.workspace_root:
                    try:
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
                        elif ws_ctx and ws_ctx.get("error"):
                            logger.warning(f"Workspace context gathering failed: {ws_ctx.get('error')}")
                            yield _sse({"type": "thinking", "content": f"Note: Could not load full workspace context - {ws_ctx.get('error')}"})
                    except Exception as ctx_error:
                        logger.warning(f"Failed to gather workspace context: {ctx_error}")
                        yield _sse({"type": "thinking", "content": "Note: Could not load full workspace context"})

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
                    pipeline_step = 0
                    async for step in pipeline.run(
                        request.message,
                        history=history,
                        context=context,
                    ):
                        # Track step counter for pipeline
                        if step.type in ("tool_call", "tool_result", "thinking"):
                            pipeline_step += 1

                        if step.type == "phase_start":
                            yield _sse({"type": "phase_start", "phase": step.phase, "content": step.content})
                        elif step.type == "phase_result":
                            yield _sse({"type": "phase_result", "phase": step.phase, "content": step.content, "model": step.model_used})
                        elif step.type == "thinking":
                            yield _sse({"type": "thinking", "content": step.content, "phase": step.phase, "step": pipeline_step})
                        elif step.type == "tool_call":
                            yield _sse({"type": "tool_call", "tool": step.tool_name, "args": step.tool_args, "phase": step.phase, "step": pipeline_step})
                        elif step.type == "tool_result":
                            result_preview = step.tool_result
                            if isinstance(result_preview, dict):
                                output = result_preview.get("output", "")
                                if isinstance(output, str) and len(output) > 2000:
                                    result_preview = {**result_preview, "output": output[:2000] + "... (truncated)"}
                            yield _sse({"type": "tool_result", "tool": step.tool_name, "result": result_preview, "duration_ms": step.duration_ms, "phase": step.phase, "step": pipeline_step})
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

                yield _sse({"type": "done", "content": final_answer, "usage": total_usage})
                yield "data: [DONE]\n\n"

        except asyncio.TimeoutError:
            logger.error(f"Agent loop timed out after {DEFAULT_AGENT_TIMEOUT}s")
            yield _sse({"type": "error", "content": f"Request timed out after {DEFAULT_AGENT_TIMEOUT} seconds. Please try a simpler task or increase timeout."})
            yield "data: [DONE]\n\n"
        except LLMConnectionError as e:
            logger.error(f"LLM connection error: {e}")
            yield _sse({"type": "error", "content": f"Cannot connect to AI provider: {e.message}"})
            yield "data: [DONE]\n\n"
        except LLMError as e:
            logger.error(f"LLM error: {e}")
            yield _sse({"type": "error", "content": f"AI provider error: {e.message}"})
            yield "data: [DONE]\n\n"
        except ToolTimeoutError as e:
            logger.error(f"Tool timeout: {e}")
            yield _sse({"type": "error", "content": f"Tool '{e.tool_name}' timed out after {e.timeout}s"})
            yield "data: [DONE]\n\n"
        except ToolExecutionError as e:
            logger.error(f"Tool execution error: {e}")
            yield _sse({"type": "error", "content": f"Tool error: {e.message}"})
            yield "data: [DONE]\n\n"
        except AgentError as e:
            logger.error(f"Agent error: {e}")
            yield _sse({"type": "error", "content": f"Agent error: {e.message}"})
            yield "data: [DONE]\n\n"
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            yield _sse({"type": "error", "content": f"Invalid request: {str(e)}"})
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Unexpected agent stream error")
            yield _sse({"type": "error", "content": f"Unexpected error: {str(e)}"})
            yield "data: [DONE]\n\n"
        finally:
            if pairing_tokens:
                clear_pairing_context(pairing_tokens)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
