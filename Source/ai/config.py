"""AI configuration and agent safety limits (RQ-04 / Agent Safety Limits).

Loaded from ``appsettings.json`` with an optional ``appsettings.local.json``
override (kept out of source control), then ``.env`` and environment-variable
overrides for the API key (``GEMINI_API_KEY``).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AIConfig:
    provider: str = "Gemini"
    model: str = "gemini-2.5-pro"
    api_key: str = ""
    max_input_tokens: int = 10_000
    max_output_tokens: int = 2_000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIConfig":
        return cls(
            provider=data.get("Provider", "Gemini"),
            model=data.get("Model", "gemini-2.5-pro"),
            api_key=data.get("ApiKey", ""),
            max_input_tokens=int(data.get("MaxInputTokens", 10_000)),
            max_output_tokens=int(data.get("MaxOutputTokens", 2_000)),
        )


@dataclass
class AgentLimits:
    max_iterations: int = 10
    max_nodes_loaded: int = 30
    max_relationship_depth: int = 3
    max_input_tokens: int = 10_000
    max_output_tokens: int = 2_000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentLimits":
        return cls(
            max_iterations=int(data.get("MaxIterations", 10)),
            max_nodes_loaded=int(data.get("MaxNodesLoaded", 30)),
            max_relationship_depth=int(data.get("MaxRelationshipDepth", 3)),
            max_input_tokens=int(data.get("MaxInputTokens", 10_000)),
            max_output_tokens=int(data.get("MaxOutputTokens", 2_000)),
        )


@dataclass
class AppSettings:
    ai: AIConfig
    agent_limits: AgentLimits


def _read_json(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_env(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    values: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(base_dir: Optional[str] = None) -> AppSettings:
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
    # Allow loading from the Source/ root where appsettings live.
    search_dirs = [base_dir, os.path.dirname(base_dir)]

    merged: dict[str, Any] = {}
    for directory in search_dirs:
        merged = _deep_merge(merged, _read_json(os.path.join(directory, "appsettings.json")))
    for directory in search_dirs:
        merged = _deep_merge(
            merged, _read_json(os.path.join(directory, "appsettings.local.json"))
        )

    ai = AIConfig.from_dict(merged.get("AI", {}))
    for directory in search_dirs:
        env_key = _read_env(os.path.join(directory, ".env")).get("GEMINI_API_KEY")
        if env_key:
            ai.api_key = env_key
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        ai.api_key = env_key

    agent_limits = AgentLimits.from_dict(merged.get("AgentLimits", {}))
    return AppSettings(ai=ai, agent_limits=agent_limits)
