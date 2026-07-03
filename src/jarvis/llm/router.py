"""
Multi-model router for JARVIS.

Classifies tasks by complexity and routes to the optimal model tier.
Integrates with the provider chain to select the best model for each request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelTier(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    STRONG = "strong"
    CODE = "code"
    # Pipeline-specific tiers
    UNDERSTAND = "understand"
    PLAN = "plan"
    IMPLEMENT = "implement"


@dataclass
class ModelRoute:
    tier: ModelTier
    provider: str
    model: str
    reason: str
    max_tokens: int = 4096
    stream: bool = True


@dataclass
class ModelCandidate:
    provider: str
    model: str


DEFAULT_TIER_MODELS: dict[ModelTier, list[ModelCandidate]] = {
    ModelTier.FAST: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    ModelTier.MEDIUM: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    ModelTier.STRONG: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    ModelTier.CODE: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    # Pipeline tiers — FreeLLM "auto" routes to the best available model.
    # The FreeLLM server's fallback chain picks from 50+ models ranked by
    # intelligence/speed, so "auto" already selects optimally per request.
    # These specific models are hints for when they're available:
    #   UNDERSTAND: Fast + high-context (Gemini Flash, GPT-OSS) for task analysis
    #   PLAN: Strong reasoning (DeepSeek V3, Kimi K2) for architecture
    #   IMPLEMENT: Best coders (Qwen3-Coder, Codestral, DeepSeek-Coder) for execution
    ModelTier.UNDERSTAND: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    ModelTier.PLAN: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
    ModelTier.IMPLEMENT: [
        ModelCandidate(provider="freellm", model="auto"),
    ],
}

_TOKEN_LIMITS: dict[ModelTier, int] = {
    ModelTier.FAST: 2048,
    ModelTier.MEDIUM: 4096,
    ModelTier.STRONG: 16384,
    ModelTier.CODE: 8192,
    ModelTier.UNDERSTAND: 4096,
    ModelTier.PLAN: 8192,
    ModelTier.IMPLEMENT: 16384,
}

_FAST_PATTERNS = [
    "what is", "what's", "define", "how many", "when did",
    "yes or no", "true or false", "list all", "name the",
    "explain briefly", "summarize", "tldr", "help",
]

_CODE_PATTERNS = [
    "write", "generate", "create a function", "implement",
    "code", "script", "fix this", "add a", "build",
    "convert", "transform", "parse", "serialize",
]

_STRONG_PATTERNS = [
    "architect", "design", "system design", "complex",
    "plan", "strategy", "optimize", "performance",
    "migration", "upgrade", "restructure", "refactor",
    "debug", "investigate", "root cause", "why does",
]


def classify_task_tier(message: str, has_code_context: bool = False) -> ModelTier:
    """Classify a user message into a model tier based on intent patterns."""
    lower = message.lower().strip()
    word_count = len(lower.split())

    if word_count <= 5 and not has_code_context:
        if any(p in lower for p in _STRONG_PATTERNS):
            return ModelTier.STRONG
        return ModelTier.FAST

    if any(p in lower for p in _STRONG_PATTERNS):
        return ModelTier.STRONG

    if any(p in lower for p in _CODE_PATTERNS) or has_code_context:
        return ModelTier.CODE

    if any(p in lower for p in _FAST_PATTERNS):
        return ModelTier.FAST

    return ModelTier.MEDIUM


class ModelRouter:
    """Routes requests to optimal model based on task classification."""

    def __init__(self, tier_models: dict[ModelTier, list[ModelCandidate]] | None = None):
        self.tier_models = tier_models or DEFAULT_TIER_MODELS

    def route(
        self,
        message: str,
        has_code_context: bool = False,
        preferred_tier: ModelTier | None = None,
    ) -> ModelRoute:
        """Determine the best model for this request."""
        tier = preferred_tier or classify_task_tier(message, has_code_context)
        candidates = self.tier_models.get(tier, self.tier_models[ModelTier.MEDIUM])

        if not candidates:
            candidates = self.tier_models[ModelTier.MEDIUM]

        best = candidates[0]
        return ModelRoute(
            tier=tier,
            provider=best.provider,
            model=best.model,
            reason=f"Classified as {tier.value} task",
            max_tokens=_TOKEN_LIMITS.get(tier, 4096),
        )

    def get_fallbacks(self, route: ModelRoute) -> list[ModelCandidate]:
        """Get fallback models for a route (excludes the primary)."""
        candidates = self.tier_models.get(route.tier, [])
        return candidates[1:]

    def get_all_candidates(self, tier: ModelTier) -> list[ModelCandidate]:
        """Get all candidates for a tier including primary."""
        return list(self.tier_models.get(tier, []))


_router_instance: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance


__all__ = [
    "ModelTier",
    "ModelRoute",
    "ModelCandidate",
    "ModelRouter",
    "classify_task_tier",
    "get_model_router",
]
