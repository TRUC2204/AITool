"""Seed Source/DemoProject with sample world-building data (kept for review)."""

from __future__ import annotations

import os

from knowledge_graph import KnowledgeGraph

PROJECT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DemoProject")


def seed() -> KnowledgeGraph:
    kg = KnowledgeGraph(PROJECT_PATH, name="One Piece World")

    luffy = kg.create_node("Luffy", "Thuyền trưởng băng Mũ Rơm, tương lai Vua Hải Tặc.")
    zoro = kg.create_node("Zoro", "Kiếm sĩ ba kiếm, mục tiêu trở thành kiếm sĩ mạnh nhất.")
    nami = kg.create_node("Nami", "Hoa tiêu, mơ vẽ bản đồ toàn thế giới.")
    sanji = kg.create_node("Sanji", "Đầu bếp, đi tìm biển All Blue.")
    shanks = kg.create_node("Shanks", "Tứ Hoàng, người truyền cảm hứng cho Luffy.")

    kg.create_relationship(luffy.id, zoro.id, ["đồng đội", "thuyền trưởng - thuyền viên"])
    kg.create_relationship(luffy.id, nami.id, ["đồng đội"])
    kg.create_relationship(luffy.id, sanji.id, ["đồng đội"])
    kg.create_relationship(shanks.id, luffy.id, ["người truyền cảm hứng", "ân nhân"])
    kg.create_relationship(zoro.id, sanji.id, ["đồng đội", "vừa hợp tác vừa cãi nhau"])

    return kg


if __name__ == "__main__":
    graph = seed()
    print(f"Seeded project at: {PROJECT_PATH}")
    print(f"Nodes: {[n.title for n in graph.list_nodes()]}")
    print(f"Relationships: {len(graph.list_relationships())}")
