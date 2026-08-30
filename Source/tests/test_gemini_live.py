"""REAL Gemini integration tests (RQ-04) — no mocking.

These tests make actual HTTPS calls to the Gemini API using the configured key.
They are SKIPPED (not failed) only when outbound network egress to the Gemini
host is unavailable, so a run behind a firewall stays honest and green while a
run with internet access truly exercises the live API.

Run explicitly:  py -3 -m unittest tests.test_gemini_live -v
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph  # noqa: E402
from ai import (  # noqa: E402
    AgentRuntime,
    AuthError,
    GeminiProvider,
    ProviderTimeoutError,
    RateLimitError,
    build_knowledge_tools,
    load_settings,
)
from ai.provider import user_text  # noqa: E402

_GEMINI_HOST = "generativelanguage.googleapis.com"


def _network_available(host: str = _GEMINI_HOST, port: int = 443, timeout: float = 5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


SETTINGS = load_settings()
HAS_KEY = bool(SETTINGS.ai.api_key)
HAS_NET = _network_available()


@unittest.skipUnless(HAS_KEY, "No Gemini API key configured")
@unittest.skipUnless(HAS_NET, f"No network egress to {_GEMINI_HOST}:443 (firewall)")
class GeminiLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = GeminiProvider(SETTINGS.ai, timeout=60)

    def _generate_or_skip_quota(self, *args, **kwargs):
        try:
            return self.provider.generate(*args, **kwargs)
        except RateLimitError as exc:
            self.skipTest(f"Gemini quota temporarily exhausted: {exc}")

    def test_valid_api_key_response(self) -> None:
        resp = self._generate_or_skip_quota([user_text("Reply with exactly: OK")])
        self.assertIsNotNone(resp.text)
        self.assertGreater(resp.usage.total_tokens, 0)

    def test_invalid_api_key(self) -> None:
        bad = load_settings().ai
        bad.api_key = "INVALID_KEY_123"
        provider = GeminiProvider(bad, timeout=30)
        with self.assertRaises((AuthError, ProviderTimeoutError)):
            provider.generate([user_text("hi")])

    def test_agent_tool_loop_end_to_end(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        kg = KnowledgeGraph(os.path.join(tmp.name, "p"), name="Live")
        kg.create_node("Luffy", "Thuyền trưởng băng Mũ Rơm, tương lai Vua Hải Tặc")
        registry = build_knowledge_tools(kg)

        agent = AgentRuntime(
            _QuotaSkippingProvider(self, self.provider),
            registry,
            SETTINGS.agent_limits,
            system_prompt=(
                "You are a world-building assistant. Use the provided tools to "
                "look up information in the knowledge graph before answering."
            ),
        )
        result = agent.run("Who is Luffy? Use the tools to find out.")
        self.assertIsNotNone(result.final_text)
        self.assertGreater(result.total_tokens, 0)
        self.assertIn(result.stop_reason, ("final_response", "max_nodes", "max_iterations"))


class _QuotaSkippingProvider:
    def __init__(self, test_case: unittest.TestCase, provider: GeminiProvider) -> None:
        self._test_case = test_case
        self._provider = provider

    def generate(self, *args, **kwargs):
        try:
            return self._provider.generate(*args, **kwargs)
        except RateLimitError as exc:
            self._test_case.skipTest(f"Gemini quota temporarily exhausted: {exc}")


if __name__ == "__main__":
    unittest.main()
