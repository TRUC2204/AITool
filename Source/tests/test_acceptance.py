"""Acceptance checklist tests (Definition of Done) for RQ-01.

Uses only the standard library (unittest) so it runs without extra packages::

    py -3 -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import IntegrityError, KnowledgeGraph  # noqa: E402


class KnowledgeGraphTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.kg = KnowledgeGraph(os.path.join(self.root, "project"), name="Test")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- Data Model / CRUD: Node --------------------------------------------
    def test_node_crud(self) -> None:
        node = self.kg.create_node(title="Luffy", content="captain")
        self.assertEqual(self.kg.get_node(node.id).title, "Luffy")

        self.kg.update_node(node.id, content="pirate king")
        self.assertEqual(self.kg.get_node(node.id).content, "pirate king")

        self.assertTrue(self.kg.delete_node(node.id))
        self.assertIsNone(self.kg.get_node(node.id))

    def test_node_unique_id(self) -> None:
        self.kg.create_node(node_id="N001", title="a")
        with self.assertRaises(IntegrityError):
            self.kg.create_node(node_id="N001", title="b")

    # -- Data Model / CRUD: Relationship ------------------------------------
    def test_relationship_crud_and_multi_metadata(self) -> None:
        a = self.kg.create_node(title="A")
        b = self.kg.create_node(title="B")
        rel = self.kg.create_relationship(
            a.id, b.id, metadata=["dong doi", "vua yeu vua han"]
        )

        self.assertEqual(
            self.kg.get_relationship(rel.id).metadata, ["dong doi", "vua yeu vua han"]
        )

        self.kg.update_relationship(rel.id, metadata=["thay tro"])
        self.assertEqual(self.kg.get_relationship(rel.id).metadata, ["thay tro"])

        self.assertTrue(self.kg.delete_relationship(rel.id))
        self.assertIsNone(self.kg.get_relationship(rel.id))

    def test_relationship_reference_validation(self) -> None:
        a = self.kg.create_node(title="A")
        with self.assertRaises(IntegrityError):
            self.kg.create_relationship(a.id, "MISSING")

    # -- Index ---------------------------------------------------------------
    def test_node_title_index(self) -> None:
        node = self.kg.create_node(title="Zoro")
        found = self.kg.find_node_by_title("Zoro")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, node.id)

    def test_relationship_index(self) -> None:
        a = self.kg.create_node(title="A")
        b = self.kg.create_node(title="B")
        rel = self.kg.create_relationship(a.id, b.id)
        ids = [r.id for r in self.kg.get_relationships_of_node(a.id)]
        self.assertIn(rel.id, ids)

    def test_rebuild_indexes(self) -> None:
        a = self.kg.create_node(title="A")
        b = self.kg.create_node(title="B")
        rel = self.kg.create_relationship(a.id, b.id)

        self.kg.rebuild_node_index()
        self.kg.rebuild_relationship_index()

        self.assertEqual(self.kg.find_node_by_title("A").id, a.id)
        self.assertIn(rel.id, [r.id for r in self.kg.get_relationships_of_node(b.id)])

    # -- Graph ---------------------------------------------------------------
    def test_traversal_inbound_outbound(self) -> None:
        a = self.kg.create_node(title="A")
        b = self.kg.create_node(title="B")
        self.kg.create_relationship(a.id, b.id)

        out = self.kg.get_connected_nodes(a.id, "outbound")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].node.id, b.id)
        self.assertEqual(out[0].direction, "outbound")

        inb = self.kg.get_connected_nodes(b.id, "inbound")
        self.assertEqual(len(inb), 1)
        self.assertEqual(inb[0].node.id, a.id)
        self.assertEqual(inb[0].direction, "inbound")

    # -- Versioning ----------------------------------------------------------
    def test_version_increment(self) -> None:
        node = self.kg.create_node(title="A")
        self.assertEqual(node.version, 1)
        self.kg.update_node(node.id, content="changed")
        self.assertEqual(self.kg.get_node(node.id).version, 2)

    # -- Persistence ---------------------------------------------------------
    def test_persistence_survives_restart(self) -> None:
        path = os.path.join(self.root, "restart")
        kg = KnowledgeGraph(path, name="P")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        kg.create_relationship(a.id, b.id, metadata=["dong doi"])

        reloaded = KnowledgeGraph(path)
        self.assertEqual({n.title for n in reloaded.list_nodes()}, {"A", "B"})
        self.assertEqual(len(reloaded.list_relationships()), 1)
        self.assertEqual(reloaded.find_node_by_title("A").id, a.id)

    # -- Import / Export -----------------------------------------------------
    def test_import_export(self) -> None:
        src = KnowledgeGraph(os.path.join(self.root, "src"))
        a = src.create_node(title="A")
        b = src.create_node(title="B")
        src.create_relationship(a.id, b.id, metadata=["dong doi"])

        nodes = src.export_nodes()
        rels = src.export_relationships()

        dst = KnowledgeGraph(os.path.join(self.root, "dst"))
        self.assertEqual(dst.import_nodes(nodes), 2)
        self.assertEqual(dst.import_relationships(rels), 1)
        self.assertEqual(dst.find_node_by_title("B").id, b.id)
        self.assertEqual(len(dst.get_relationships_of_node(a.id)), 1)


if __name__ == "__main__":
    unittest.main()
