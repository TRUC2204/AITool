"""Demo showing the RQ-01 Knowledge Graph storage foundation end to end."""

from __future__ import annotations

import os
import tempfile

from knowledge_graph import KnowledgeGraph


def main() -> None:
    project_path = os.path.join(tempfile.gettempdir(), "kg_demo_project")
    kg = KnowledgeGraph(project_path, name="Demo World")

    luffy = kg.create_node(title="Luffy", content="Captain of the Straw Hats")
    zoro = kg.create_node(title="Zoro", content="Swordsman")

    kg.create_relationship(luffy.id, zoro.id, metadata=["dong doi", "thay tro"])

    print(f"Project stored at: {project_path}")
    print(f"Nodes: {[n.title for n in kg.list_nodes()]}")

    found = kg.find_node_by_title("Zoro")
    print(f"find_node_by_title('Zoro') -> {found.id if found else None}")

    for connected in kg.get_connected_nodes(luffy.id):
        print(
            f"{luffy.title} --{connected.relationship.metadata}--> "
            f"{connected.node.title} ({connected.direction})"
        )

    # Reload from disk to prove persistence survives a restart.
    reloaded = KnowledgeGraph(project_path)
    print(f"Reloaded nodes after restart: {[n.title for n in reloaded.list_nodes()]}")


if __name__ == "__main__":
    main()
