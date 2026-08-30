"""Real end-to-end agent demo against Source/DemoProject (needs internet).

Run on a network that allows HTTPS to the Gemini API:

    py -3 seed_demo.py       # once, to create DemoProject
    py -3 run_agent_demo.py  # real Gemini agent run

The API key is read from Source/.env (or the GEMINI_API_KEY env var).
"""

from __future__ import annotations

import os

from ai import AgentRuntime, GeminiProvider, build_knowledge_tools, load_settings
from knowledge_graph import KnowledgeGraph

PROJECT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DemoProject")

SYSTEM_PROMPT = (
    "You are a world-building assistant for a fiction knowledge graph. "
    "Always use the provided tools (SearchNode, GetNode, GetRelatedNodes) to "
    "ground your answers in the stored data. You may CreateNode/UpdateNode/"
    "DeleteNode when the user asks to change the world. Stop once you have "
    "enough context to answer."
)


def main() -> None:
    settings = load_settings()
    if not settings.ai.api_key:
        raise SystemExit("No API key. Set GEMINI_API_KEY in Source/.env or as an environment variable.")

    kg = KnowledgeGraph(PROJECT_PATH)
    registry = build_knowledge_tools(kg)
    provider = GeminiProvider(settings.ai, timeout=60)
    agent = AgentRuntime(provider, registry, settings.agent_limits, system_prompt=SYSTEM_PROMPT)

    question = "Who inspired Luffy, and who are his crew mates? Use the tools."
    print(f"Q: {question}\n")
    result = agent.run(question)

    print(f"A: {result.final_text}\n")
    print(f"stop_reason={result.stop_reason} iterations={result.iterations}")
    print(f"tokens: in={result.input_tokens} out={result.output_tokens} total={result.total_tokens}")
    print("tool calls:")
    for call in result.tool_calls:
        print(f"  [{call.iteration}] {call.name}({call.args}) ok={call.ok}")


if __name__ == "__main__":
    main()
