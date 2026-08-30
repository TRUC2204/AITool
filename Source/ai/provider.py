"""AI Provider Layer (RQ-04): IAIProvider abstraction and a real GeminiProvider.

GeminiProvider talks to the Google Generative Language REST API directly (no
SDK dependency) using the standard library, and supports function/tool calling.
"""

from __future__ import annotations

import abc
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import AIConfig
from .token_control import TokenUsage


class AIProviderError(Exception):
    """Base class for provider failures."""


class AuthError(AIProviderError):
    """Invalid or unauthorized API key."""


class RateLimitError(AIProviderError):
    """Provider returned HTTP 429."""


class ProviderTimeoutError(AIProviderError):
    """Request exceeded the timeout."""


@dataclass
class FunctionCall:
    name: str
    args: dict[str, Any]
    # Gemini "thinking" models return an opaque signature that must be echoed
    # back with the functionCall on the next turn, or the API rejects it (400).
    thought_signature: Optional[str] = None


@dataclass
class ProviderResponse:
    text: Optional[str] = None
    function_calls: list[FunctionCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.function_calls)


# -- Gemini content builders -------------------------------------------------
def user_text(text: str) -> dict[str, Any]:
    return {"role": "user", "parts": [{"text": text}]}


def model_function_call(
    name: str, args: dict[str, Any], thought_signature: Optional[str] = None
) -> dict[str, Any]:
    part: dict[str, Any] = {"functionCall": {"name": name, "args": args}}
    if thought_signature:
        part["thoughtSignature"] = thought_signature
    return {"role": "model", "parts": [part]}


def function_response(name: str, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "user",
        "parts": [{"functionResponse": {"name": name, "response": response}}],
    }


class IAIProvider(abc.ABC):
    """Provider abstraction so the agent runtime is model-agnostic."""

    @abc.abstractmethod
    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        ...


class GeminiProvider(IAIProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, config: AIConfig, timeout: int = 60) -> None:
        if not config.api_key:
            raise AuthError("Missing Gemini API key")
        self._config = config
        self._timeout = timeout
        self._ssl_context = ssl.create_default_context()

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_output_tokens or self._config.max_output_tokens
            },
        }
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]

        payload = json.dumps(body).encode("utf-8")
        url = f"{self.BASE_URL}/{self._config.model}:generateContent"
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._config.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout, context=self._ssl_context
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in (400, 401, 403) and "API_KEY_INVALID" in detail:
                raise AuthError(f"Unauthorized ({exc.code}): {detail}") from exc
            if exc.code in (401, 403):
                raise AuthError(f"Unauthorized ({exc.code}): {detail}") from exc
            if exc.code == 429:
                raise RateLimitError(f"Rate limited: {detail}") from exc
            raise AIProviderError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderTimeoutError(str(exc)) from exc

        return self._parse(data)

    @staticmethod
    def _parse(data: dict[str, Any]) -> ProviderResponse:
        response = ProviderResponse(raw=data)

        usage_meta = data.get("usageMetadata", {})
        response.usage = TokenUsage(
            input_tokens=int(usage_meta.get("promptTokenCount", 0)),
            output_tokens=int(usage_meta.get("candidatesTokenCount", 0)),
        )

        candidates = data.get("candidates", [])
        if not candidates:
            return response

        candidate = candidates[0]
        response.finish_reason = candidate.get("finishReason")
        text_parts: list[str] = []
        for part in candidate.get("content", {}).get("parts", []):
            if "functionCall" in part:
                call = part["functionCall"]
                response.function_calls.append(
                    FunctionCall(
                        name=call.get("name", ""),
                        args=call.get("args", {}) or {},
                        thought_signature=part.get("thoughtSignature"),
                    )
                )
            elif "text" in part:
                text_parts.append(part["text"])

        if text_parts:
            response.text = "".join(text_parts)
        return response
