"""AI Tool Calling (RQ-04/05/06): tool registration, validation and execution.

A ToolRegistry exposes callable tools to the agent. Each tool carries a Gemini
``functionDeclaration`` (name, description, JSON-schema parameters) and a Python
handler. Execution parses the arguments, validates required parameters and
returns a plain dict result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class ToolError(Exception):
    """Base class for tool errors."""


class ToolNotFoundError(ToolError):
    """Requested tool name is not registered."""


class ToolValidationError(ToolError):
    """Arguments failed validation (e.g. missing required parameter)."""


class ToolExecutionError(ToolError):
    """The tool handler raised while executing."""


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema (Gemini function parameters)
    handler: ToolHandler
    required: list[str] = field(default_factory=list)

    def to_function_declaration(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ToolResult:
    name: str
    ok: bool
    result: dict[str, Any]
    error: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ToolValidationError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def function_declarations(self) -> list[dict[str, Any]]:
        return [spec.to_function_declaration() for spec in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolNotFoundError(f"Unknown tool: {name}")

        args = args or {}
        missing = [p for p in spec.required if p not in args or args[p] in (None, "")]
        if missing:
            raise ToolValidationError(
                f"Tool '{name}' missing required parameter(s): {', '.join(missing)}"
            )

        try:
            result = spec.handler(args)
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface handler failure as tool error
            raise ToolExecutionError(f"Tool '{name}' failed: {exc}") from exc

        return ToolResult(name=name, ok=True, result=result)
