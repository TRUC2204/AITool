"""Agent Runtime (RQ-04): the tool-calling loop.

    User Request -> Gemini -> need tool? -> execute tool -> return data ->
    Gemini -> ... -> final response

Enforces the Agent Safety Limits: max iterations, max nodes loaded, and the
token budget. Stops on a final text answer, when a limit is hit, or when the
provider returns nothing actionable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .config import AgentLimits
from .provider import (
    FunctionCall,
    IAIProvider,
    ProviderResponse,
    function_response,
    model_function_call,
    user_text,
)
from .token_control import UsageMonitor
from .tools import ToolError, ToolRegistry


@dataclass
class ToolCallLog:
    iteration: int
    name: str
    args: dict[str, Any]
    ok: bool
    result: dict[str, Any]
    error: Optional[str] = None


@dataclass
class AgentResult:
    final_text: Optional[str]
    iterations: int
    stop_reason: str  # "final_response" | "max_iterations" | "max_nodes" | "empty_response"
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AgentRuntime:
    def __init__(
        self,
        provider: IAIProvider,
        tools: ToolRegistry,
        limits: AgentLimits,
        usage_monitor: Optional[UsageMonitor] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._limits = limits
        self._usage = usage_monitor or UsageMonitor()
        self._system_prompt = system_prompt

    @property
    def usage(self) -> UsageMonitor:
        return self._usage

    def run(self, user_request: str) -> AgentResult:
        contents: list[dict[str, Any]] = []
        if self._system_prompt:
            contents.append(user_text(self._system_prompt))
        contents.append(user_text(user_request))

        declarations = self._tools.function_declarations()
        tool_calls: list[ToolCallLog] = []
        nodes_loaded = 0

        for iteration in range(1, self._limits.max_iterations + 1):
            response: ProviderResponse = self._provider.generate(
                contents,
                tools=declarations,
                max_output_tokens=self._limits.max_output_tokens,
            )
            self._usage.add(response.usage)

            if not response.has_tool_calls:
                return self._finish(
                    response.text, iteration, "final_response", tool_calls
                )

            # Execute every requested tool call this turn.
            for call in response.function_calls:
                contents.append(model_function_call(call.name, call.args))
                log = self._execute(call, iteration)
                tool_calls.append(log)
                contents.append(
                    function_response(call.name, log.result if log.ok else {"error": log.error})
                )
                if log.ok and call.name in ("GetNode", "GetRelatedNodes", "SearchNode"):
                    nodes_loaded += self._count_loaded(log.result)

            if nodes_loaded >= self._limits.max_nodes_loaded:
                # Ask the model for a final answer with what it has.
                contents.append(
                    user_text(
                        "Node load limit reached. Provide your final answer now "
                        "using the data already retrieved."
                    )
                )
                final = self._provider.generate(
                    contents, max_output_tokens=self._limits.max_output_tokens
                )
                self._usage.add(final.usage)
                return self._finish(
                    final.text, iteration, "max_nodes", tool_calls
                )

        return self._finish(None, self._limits.max_iterations, "max_iterations", tool_calls)

    def _execute(self, call: FunctionCall, iteration: int) -> ToolCallLog:
        try:
            result = self._tools.execute(call.name, call.args)
            return ToolCallLog(
                iteration=iteration,
                name=call.name,
                args=call.args,
                ok=True,
                result=result.result,
            )
        except ToolError as exc:
            return ToolCallLog(
                iteration=iteration,
                name=call.name,
                args=call.args,
                ok=False,
                result={},
                error=str(exc),
            )

    @staticmethod
    def _count_loaded(result: dict[str, Any]) -> int:
        if "count" in result and isinstance(result["count"], int):
            return result["count"]
        if result.get("found"):
            return 1
        return 0

    def _finish(
        self,
        text: Optional[str],
        iteration: int,
        reason: str,
        tool_calls: list[ToolCallLog],
    ) -> AgentResult:
        if text is None and reason == "final_response":
            reason = "empty_response"
        snapshot = self._usage.snapshot()
        return AgentResult(
            final_text=text,
            iterations=iteration,
            stop_reason=reason,
            tool_calls=tool_calls,
            input_tokens=snapshot.input_tokens,
            output_tokens=snapshot.output_tokens,
        )
