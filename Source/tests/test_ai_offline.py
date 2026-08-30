"""Offline tests for AI tool calling, token control, agent loop and RQ-06 tools.

These do not call the network. The agent-loop tests use a scripted in-process
provider (a test double) purely to verify loop mechanics; real Gemini access is
verified separately in test_gemini_live.py.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph  # noqa: E402
from ai import (  # noqa: E402
    AgentLimits,
    AgentRuntime,
    InputTokenControl,
    OutputTokenControl,
    TokenUsage,
    UsageMonitor,
    build_knowledge_tools,
    estimate_tokens,
)
from ai.provider import (  # noqa: E402
    FunctionCall,
    IAIProvider,
    ProviderResponse,
)
from ai.tools import (  # noqa: E402
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistry,
    ToolSpec,
    ToolValidationError,
)


class ScriptedProvider(IAIProvider):
    """Returns a pre-scripted sequence of responses (loop-mechanics double)."""

    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


class TokenControlTests(unittest.TestCase):
    def test_estimate_tokens(self) -> None:
        self.assertEqual(estimate_tokens(""), 0)
        self.assertGreater(estimate_tokens("hello world foobar"), 0)

    def test_context_exceeds_limit(self) -> None:
        control = InputTokenControl(max_input_tokens=5)  # ~20 chars
        big = "x" * 400
        self.assertTrue(control.exceeds_budget(big))
        trimmed = control.truncate_to_budget(big)
        self.assertLessEqual(estimate_tokens(trimmed), 5)

    def test_truncate_segments_keeps_recent(self) -> None:
        control = InputTokenControl(max_input_tokens=10)
        segments = ["a" * 40, "b" * 40, "c" * 8]
        kept, trimmed = control.truncate_segments(segments)
        self.assertTrue(trimmed)
        self.assertIn("c" * 8, kept)

    def test_output_exceeds_limit(self) -> None:
        control = OutputTokenControl(max_output_tokens=2000)
        self.assertEqual(control.clamp(5000), 2000)
        self.assertEqual(control.clamp(100), 100)
        self.assertEqual(control.clamp(None), 2000)

    def test_usage_tracking_accurate(self) -> None:
        monitor = UsageMonitor()
        monitor.add(TokenUsage(100, 20))
        monitor.add(TokenUsage(50, 10))
        self.assertEqual(monitor.input_tokens, 150)
        self.assertEqual(monitor.output_tokens, 30)
        self.assertEqual(monitor.total_tokens, 180)


class ToolCallingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="Tools")
        self.registry = build_knowledge_tools(self.kg)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tool_called_correctly(self) -> None:
        node = self.kg.create_node("Luffy", "captain")
        result = self.registry.execute("GetNode", {"nodeId": node.id})
        self.assertTrue(result.ok)
        self.assertEqual(result.result["title"], "Luffy")

    def test_tool_name_not_found(self) -> None:
        with self.assertRaises(ToolNotFoundError):
            self.registry.execute("NoSuchTool", {})

    def test_parameter_invalid(self) -> None:
        with self.assertRaises(ToolValidationError):
            self.registry.execute("GetNode", {})  # missing nodeId

    def test_tool_exception(self) -> None:
        def boom(_args: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("kaboom")

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="Boom",
                description="always fails",
                parameters={"type": "object", "properties": {}},
                handler=boom,
            )
        )
        with self.assertRaises(ToolExecutionError):
            registry.execute("Boom", {})


class DataModificationTests(unittest.TestCase):
    """RQ-06: create / update / delete via tools."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="Mod")
        self.registry = build_knowledge_tools(self.kg)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_success(self) -> None:
        result = self.registry.execute("CreateNode", {"title": "Ace", "content": "fire"})
        self.assertTrue(result.result["created"])
        self.assertIsNotNone(self.kg.get_node(result.result["id"]))

    def test_update_success(self) -> None:
        node = self.kg.create_node("Ace", "fire")
        result = self.registry.execute(
            "UpdateNode", {"nodeId": node.id, "content": "fire fist"}
        )
        self.assertTrue(result.result["updated"])
        self.assertEqual(self.kg.get_node(node.id).content, "fire fist")

    def test_delete_success(self) -> None:
        node = self.kg.create_node("Ace", "fire")
        result = self.registry.execute("DeleteNode", {"nodeId": node.id})
        self.assertTrue(result.result["deleted"])
        self.assertIsNone(self.kg.get_node(node.id))

    def test_node_not_found(self) -> None:
        update = self.registry.execute("UpdateNode", {"nodeId": "NOPE"})
        self.assertFalse(update.result["updated"])
        delete = self.registry.execute("DeleteNode", {"nodeId": "NOPE"})
        self.assertFalse(delete.result["deleted"])


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="Loop")
        self.kg.create_node("Luffy", "captain")
        self.registry = build_knowledge_tools(self.kg)
        self.limits = AgentLimits(max_iterations=5, max_nodes_loaded=30)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_single_loop_final_answer(self) -> None:
        provider = ScriptedProvider(
            [ProviderResponse(text="Done", usage=TokenUsage(10, 5))]
        )
        agent = AgentRuntime(provider, self.registry, self.limits)
        result = agent.run("hi")
        self.assertEqual(result.stop_reason, "final_response")
        self.assertEqual(result.final_text, "Done")
        self.assertEqual(result.iterations, 1)

    def test_multi_loop_then_answer(self) -> None:
        provider = ScriptedProvider(
            [
                ProviderResponse(
                    function_calls=[FunctionCall("SearchNode", {"query": "Luffy"})],
                    usage=TokenUsage(20, 8),
                ),
                ProviderResponse(text="Found Luffy", usage=TokenUsage(15, 6)),
            ]
        )
        agent = AgentRuntime(provider, self.registry, self.limits)
        result = agent.run("find luffy")
        self.assertEqual(result.final_text, "Found Luffy")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].name, "SearchNode")
        self.assertTrue(result.tool_calls[0].ok)
        self.assertEqual(result.total_tokens, 20 + 8 + 15 + 6)

    def test_iteration_limit(self) -> None:
        # Provider always asks for a tool -> never finalizes.
        provider = ScriptedProvider(
            [
                ProviderResponse(
                    function_calls=[FunctionCall("SearchNode", {"query": "x"})],
                    usage=TokenUsage(5, 1),
                )
            ]
        )
        agent = AgentRuntime(provider, self.registry, AgentLimits(max_iterations=3))
        result = agent.run("loop forever")
        self.assertEqual(result.stop_reason, "max_iterations")
        self.assertEqual(result.iterations, 3)


if __name__ == "__main__":
    unittest.main()
