"""Release acceptance tests for RQ-04, RQ-05, and RQ-06.

The RQ-05/RQ-06 checks are evidence-based: a correct final answer is not enough.
The tests require a debug log proving which internal nodes and relationships
were accessed before the answer or modification result is accepted.
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
    FunctionCall,
    IAIProvider,
    ProviderResponse,
    ToolCallLog,
    TokenUsage,
    build_knowledge_tools,
    format_agent_debug_log,
    format_tool_call_debug_log,
    load_settings,
)


class ScriptedProvider(IAIProvider):
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        max_output_tokens: Optional[int] = None,
    ) -> ProviderResponse:
        self.calls.append(
            {
                "contents": contents,
                "tools": tools or [],
                "max_output_tokens": max_output_tokens,
            }
        )
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


class ReleaseAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "release"), name="Release")
        self.character_a = self.kg.create_node("Character_A", "Young prince")
        self.character_b = self.kg.create_node("Character_B", "Father of Character_A")
        self.kingdom_a = self.kg.create_node("Kingdom_A", "Home kingdom")
        self.kg.create_relationship(self.character_a.id, self.character_b.id, ["Father"])
        self.kg.create_relationship(self.character_a.id, self.kingdom_a.id, ["LiveIn"])
        self.registry = build_knowledge_tools(self.kg)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rq04_configuration_uses_env_key_and_working_model(self) -> None:
        settings = load_settings()
        self.assertEqual(settings.ai.provider, "Gemini")
        self.assertEqual(settings.ai.model, "gemini-2.5-flash")
        self.assertTrue(settings.ai.api_key)
        self.assertEqual(settings.agent_limits.max_output_tokens, 2000)

    def test_rq05_release_data_access_requires_trace_log(self) -> None:
        provider = ScriptedProvider(
            [
                ProviderResponse(
                    function_calls=[FunctionCall("SearchNode", {"query": "Character_A"})],
                    usage=TokenUsage(12, 4),
                ),
                ProviderResponse(
                    function_calls=[FunctionCall("GetNode", {"nodeId": self.character_a.id})],
                    usage=TokenUsage(18, 5),
                ),
                ProviderResponse(
                    function_calls=[
                        FunctionCall(
                            "GetRelatedNodes",
                            {"nodeId": self.character_a.id, "maxDepth": 1},
                        )
                    ],
                    usage=TokenUsage(24, 6),
                ),
                ProviderResponse(
                    text="Cha của Character_A là Character_B.",
                    usage=TokenUsage(30, 8),
                ),
            ]
        )
        agent = AgentRuntime(provider, self.registry, AgentLimits(max_iterations=5))

        result = agent.run("Cha của Character_A là ai?")
        debug_log = format_agent_debug_log(
            "Cha của Character_A là ai?", result, provider="Gemini", model="gemini-2.5-flash"
        )

        self.assertEqual(result.stop_reason, "final_response")
        self.assertGreaterEqual(len(provider.calls), 4)
        self.assertIn("[SEARCH]", debug_log)
        self.assertIn("Keyword: Character_A", debug_log)
        self.assertIn("Matched Nodes:", debug_log)
        self.assertIn("[NODE ACCESS]", debug_log)
        self.assertIn("Load Node: Character_A", debug_log)
        self.assertIn("[RELATIONSHIP TRAVERSAL]", debug_log)
        self.assertIn("-> Father", debug_log)
        self.assertIn("-> Character_B", debug_log)
        self.assertIn("[CONTEXT GENERATED]", debug_log)
        self.assertIn("Included Nodes:", debug_log)
        self.assertIn("Character_B", debug_log)
        self.assertIn("Kingdom_A", debug_log)
        self.assertIn("[AI REQUEST]", debug_log)
        self.assertIn("Provider: Gemini", debug_log)
        self.assertIn("Request Sent: Success", debug_log)
        self.assertIn("[AI RESPONSE]", debug_log)
        self.assertIn("Response Received: Success", debug_log)

    def test_rq06_modification_requires_tool_and_storage_log(self) -> None:
        create_result = self.registry.execute(
            "CreateNode", {"title": "Kingdom_B", "content": "Neighbor kingdom"}
        )
        create_call = ToolCallLog(
            1, "CreateNode", {"title": "Kingdom_B", "content": "Neighbor kingdom"}, True, create_result.result
        )

        update_result = self.registry.execute(
            "UpdateNode",
            {"nodeId": self.character_a.id, "content": "Young prince of Kingdom A"},
        )
        update_call = ToolCallLog(
            2,
            "UpdateNode",
            {"nodeId": self.character_a.id, "content": "Young prince of Kingdom A"},
            True,
            update_result.result,
        )

        delete_result = self.registry.execute("DeleteNode", {"nodeId": create_result.result["id"]})
        delete_call = ToolCallLog(
            3, "DeleteNode", {"nodeId": create_result.result["id"]}, True, delete_result.result
        )

        modification_log = "\n\n".join(
            [
                format_tool_call_debug_log(create_call),
                format_tool_call_debug_log(update_call),
                format_tool_call_debug_log(delete_call),
            ]
        )

        self.assertIsNotNone(self.kg.get_node(self.character_a.id))
        self.assertEqual(self.kg.get_node(self.character_a.id).content, "Young prince of Kingdom A")
        self.assertIsNone(self.kg.get_node(create_result.result["id"]))
        self.assertIn("[AI TOOL CALL]", modification_log)
        self.assertIn("CreateNode", modification_log)
        self.assertIn("Node Created", modification_log)
        self.assertIn("UpdateNode", modification_log)
        self.assertIn("[OLD VALUE]", modification_log)
        self.assertIn("Young prince", modification_log)
        self.assertIn("[NEW VALUE]", modification_log)
        self.assertIn("Young prince of Kingdom A", modification_log)
        self.assertIn("DeleteNode", modification_log)
        self.assertIn("Result: Success", modification_log)


if __name__ == "__main__":
    unittest.main()