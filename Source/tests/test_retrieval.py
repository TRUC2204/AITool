"""RQ-03 Knowledge Retrieval tests (offline, no AI)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph  # noqa: E402
from retrieval import (  # noqa: E402
    KnowledgeRetrievalService,
    RetrievalLimits,
    SearchService,
)


class RetrievalTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.kg = KnowledgeGraph(os.path.join(self._tmp.name, "p"), name="Retrieval")
        self.luffy = self.kg.create_node("Luffy", "Thuyền trưởng Mũ Rơm")
        self.zoro = self.kg.create_node("Zoro", "Kiếm sĩ")
        self.nami = self.kg.create_node("Nami", "Hoa tiêu")
        self.kg.create_relationship(self.luffy.id, self.zoro.id, ["đồng đội"])
        self.kg.create_relationship(self.zoro.id, self.nami.id, ["đồng đội"])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_search_success(self) -> None:
        hits = SearchService(self.kg).search_by_keyword("kiếm")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].id, self.zoro.id)

    def test_search_no_result(self) -> None:
        hits = SearchService(self.kg).search_by_keyword("khong-ton-tai-xyz")
        self.assertEqual(hits, [])

    def test_search_by_metadata(self) -> None:
        hits = SearchService(self.kg).search_by_metadata("đồng đội")
        ids = {h.id for h in hits}
        self.assertIn(self.luffy.id, ids)
        self.assertIn(self.zoro.id, ids)

    def test_load_related_node(self) -> None:
        service = KnowledgeRetrievalService(self.kg)
        result = service.get_related_nodes(self.luffy.id)
        titles = {r.node.title for r in result.related}
        self.assertIn("Zoro", titles)  # depth 1
        self.assertIn("Nami", titles)  # depth 2

    def test_detect_circular_relationship(self) -> None:
        # Close the loop: Nami -> Luffy makes A-B-C-A a cycle.
        self.kg.create_relationship(self.nami.id, self.luffy.id, ["đồng đội"])
        service = KnowledgeRetrievalService(self.kg)
        result = service.get_related_nodes(self.luffy.id)
        self.assertTrue(result.visited_circular)

    def test_stop_when_exceed_depth(self) -> None:
        service = KnowledgeRetrievalService(
            self.kg, RetrievalLimits(max_depth=1)
        )
        result = service.get_related_nodes(self.luffy.id)
        titles = {r.node.title for r in result.related}
        self.assertIn("Zoro", titles)
        self.assertNotIn("Nami", titles)  # blocked by depth 1
        self.assertEqual(result.stopped_reason, "max_depth")

    def test_stop_when_exceed_node_limit(self) -> None:
        service = KnowledgeRetrievalService(
            self.kg, RetrievalLimits(max_nodes=1)
        )
        result = service.get_related_nodes(self.luffy.id)
        self.assertEqual(len(result.related), 1)
        self.assertEqual(result.stopped_reason, "max_nodes")


if __name__ == "__main__":
    unittest.main()
