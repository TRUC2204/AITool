"""Agent Runtime + Knowledge Retrieval + controlled Gemini integration.

Phase 0 (RQ-04/05/06): provider, tools, agent loop, token control, context.
Phase 1: proposal-mode partner tools, cost tracking, observed provider.
"""

from __future__ import annotations

from .agent import AgentResult, AgentRuntime, ToolCallLog
from .config import AgentLimits, AIConfig, AppSettings, load_settings
from .context_assembly import (
    build_node_context,
    build_relationship_context,
    merge_context,
)
from .cost import CostRates, CostTracker, optimize_prompt
from .knowledge_tools import build_knowledge_tools
from .observed_provider import ObservedProvider
from .partner_tools import ToolContext, build_partner_tools
from .provider import (
    AIProviderError,
    AuthError,
    FunctionCall,
    GeminiProvider,
    IAIProvider,
    ProviderResponse,
    ProviderTimeoutError,
    RateLimitError,
)
from .token_control import (
    InputTokenControl,
    OutputTokenControl,
    TokenUsage,
    UsageMonitor,
    estimate_tokens,
)
from .tools import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistry,
    ToolSpec,
    ToolValidationError,
)
from .trace_log import format_agent_debug_log, format_tool_call_debug_log

__all__ = [
    "load_settings",
    "AppSettings",
    "AIConfig",
    "AgentLimits",
    "GeminiProvider",
    "IAIProvider",
    "ProviderResponse",
    "FunctionCall",
    "AIProviderError",
    "AuthError",
    "RateLimitError",
    "ProviderTimeoutError",
    "ToolRegistry",
    "ToolSpec",
    "ToolNotFoundError",
    "ToolValidationError",
    "ToolExecutionError",
    "build_knowledge_tools",
    "build_partner_tools",
    "ToolContext",
    "ObservedProvider",
    "CostTracker",
    "CostRates",
    "optimize_prompt",
    "AgentRuntime",
    "AgentResult",
    "ToolCallLog",
    "UsageMonitor",
    "TokenUsage",
    "InputTokenControl",
    "OutputTokenControl",
    "estimate_tokens",
    "build_node_context",
    "build_relationship_context",
    "merge_context",
    "format_agent_debug_log",
    "format_tool_call_debug_log",
]
