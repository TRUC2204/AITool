"""Extended acceptance tests for RQ-01 (Definition of Done mo rong).

Covers the P1 (required) and P2 (hardening) scenarios. Standard library only::

    py -3 -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import IntegrityError, KnowledgeGraph  # noqa: E402


class ExtendedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _kg(self, name: str) -> KnowledgeGraph:
        return KnowledgeGraph(os.path.join(self.root, name), name=name)

    # -- P1.1 Project Isolation ---------------------------------------------
    def test_project_isolation(self) -> None:
        project_a = self._kg("ProjectA")
        project_b = self._kg("ProjectB")
        project_a.create_node(title="Luffy")

        self.assertIsNotNone(project_a.find_node_by_title("Luffy"))
        self.assertIsNone(project_b.find_node_by_title("Luffy"))

    # -- P1.2 Relationship Version Increment --------------------------------
    def test_relationship_version_increment(self) -> None:
        kg = self._kg("rel_ver")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        rel = kg.create_relationship(a.id, b.id, metadata=["x"])
        self.assertEqual(rel.version, 1)

        kg.update_relationship(rel.id, metadata=["y"])
        self.assertEqual(kg.get_relationship(rel.id).version, 2)

    # -- P1.3 Delete Node Impact (Option 1: cascade) ------------------------
    def test_delete_node_removes_relationships(self) -> None:
        kg = self._kg("del_impact")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        rel = kg.create_relationship(a.id, b.id)

        kg.delete_node(b.id)

        self.assertIsNone(kg.get_node(b.id))
        self.assertIsNone(kg.get_relationship(rel.id))
        self.assertEqual(kg.get_relationships_of_node(a.id), [])

    # -- P1.4 Unicode Node Content ------------------------------------------
    def test_unicode_node_content(self) -> None:
        path = os.path.join(self.root, "unicode_node")
        kg = KnowledgeGraph(path, name="U")
        node = kg.create_node(title="Luffy", content="Vua Hải Tặc tương lai 海賊王 海贼王")

        reloaded = KnowledgeGraph(path)
        loaded = reloaded.get_node(node.id)
        self.assertEqual(loaded.content, "Vua Hải Tặc tương lai 海賊王 海贼王")
        self.assertEqual(loaded.title, "Luffy")

    # -- P1.5 Unicode Relationship Metadata ---------------------------------
    def test_unicode_relationship_metadata(self) -> None:
        path = os.path.join(self.root, "unicode_meta")
        kg = KnowledgeGraph(path, name="U")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        metadata = ["đồng đội", "vừa yêu vừa hận", "người thay đổi số phận"]
        rel = kg.create_relationship(a.id, b.id, metadata=metadata)

        reloaded = KnowledgeGraph(path)
        self.assertEqual(reloaded.get_relationship(rel.id).metadata, metadata)

    # -- P2.1 Restart + Rebuild Index ---------------------------------------
    def test_restart_then_rebuild_index(self) -> None:
        path = os.path.join(self.root, "restart_rebuild")
        kg = KnowledgeGraph(path, name="R")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        kg.create_relationship(a.id, b.id)

        reloaded = KnowledgeGraph(path)
        reloaded.rebuild_node_index()
        reloaded.rebuild_relationship_index()

        self.assertEqual(reloaded.find_node_by_title("A").id, a.id)
        self.assertEqual(len(reloaded.get_relationships_of_node(a.id)), 1)

    # -- P2.2 Auto Node ID Generation ---------------------------------------
    def test_auto_node_id_generation(self) -> None:
        kg = self._kg("auto_node")
        ids = [kg.create_node(title=f"n{i}").id for i in range(3)]
        self.assertEqual(ids, ["N001", "N002", "N003"])
        self.assertEqual(len(set(ids)), 3)

    # -- P2.3 Auto Relationship ID Generation -------------------------------
    def test_auto_relationship_id_generation(self) -> None:
        kg = self._kg("auto_rel")
        nodes = [kg.create_node(title=f"n{i}") for i in range(4)]
        ids = [
            kg.create_relationship(nodes[0].id, nodes[i].id).id for i in range(1, 4)
        ]
        self.assertEqual(ids, ["R001", "R002", "R003"])

    # -- P2.4 Multiple Relationships ----------------------------------------
    def test_multiple_relationships(self) -> None:
        kg = self._kg("multi_rel")
        a = kg.create_node(title="A")
        for title in ("B", "C", "D", "E"):
            other = kg.create_node(title=title)
            kg.create_relationship(a.id, other.id)
        self.assertEqual(len(kg.get_relationships_of_node(a.id)), 4)

    # -- P2.5 Bidirectional Traversal ---------------------------------------
    def test_bidirectional_traversal(self) -> None:
        kg = self._kg("bidir")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        c = kg.create_node(title="C")
        kg.create_relationship(a.id, b.id)  # A -> B
        kg.create_relationship(b.id, c.id)  # B -> C

        connected = {cn.node.title for cn in kg.get_connected_nodes(b.id, "both")}
        self.assertEqual(connected, {"A", "C"})

    # -- P2.6 Import / Export Preserve IDs ----------------------------------
    def test_import_export_preserve_ids(self) -> None:
        src = self._kg("src")
        a = src.create_node(title="A")
        b = src.create_node(title="B")
        self.assertEqual([a.id, b.id], ["N001", "N002"])

        dst = self._kg("dst")
        dst.import_nodes(src.export_nodes())

        self.assertIsNotNone(dst.get_node("N001"))
        self.assertIsNotNone(dst.get_node("N002"))
        self.assertEqual({n.id for n in dst.list_nodes()}, {"N001", "N002"})

    # -- P2.7 Empty Project -------------------------------------------------
    def test_empty_project(self) -> None:
        kg = self._kg("empty")
        self.assertEqual(kg.list_nodes(), [])
        self.assertEqual(kg.list_relationships(), [])

    # -- P2.8 Rebuild Index After Index File Loss ---------------------------
    def test_rebuild_index_after_index_deletion(self) -> None:
        path = os.path.join(self.root, "index_loss")
        kg = KnowledgeGraph(path, name="IL")
        a = kg.create_node(title="A")
        b = kg.create_node(title="B")
        kg.create_relationship(a.id, b.id)

        os.remove(kg.storage.node_title_index_file)
        os.remove(kg.storage.relationship_index_file)

        reloaded = KnowledgeGraph(path)
        reloaded.rebuild_node_index()
        reloaded.rebuild_relationship_index()

        self.assertEqual(reloaded.find_node_by_title("A").id, a.id)
        self.assertEqual(len(reloaded.get_relationships_of_node(a.id)), 1)


if __name__ == "__main__":
    unittest.main()
