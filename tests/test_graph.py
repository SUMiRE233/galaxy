from __future__ import annotations

import unittest

import pandas as pd

from tests.helpers import load_script


demo_module = load_script("00_generate_demo_data.py", "test_demo_module")
graph_module = load_script("04_build_graph.py", "test_graph_module")


class BuildGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = demo_module.generate_demo(count=12, seed=7)

    def test_builds_unique_valid_graph(self) -> None:
        graph = graph_module.build_graph(self.frame, top_k=3)
        node_ids = {node["id"] for node in graph["nodes"]}
        pairs = [tuple(sorted((link["source"], link["target"]))) for link in graph["links"]]

        self.assertEqual(len(node_ids), 12)
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue(all(source != target for source, target in pairs))
        self.assertTrue(all(source in node_ids and target in node_ids for source, target in pairs))
        self.assertTrue(all(len(items) == 3 for items in graph["recommendations"].values()))
        self.assertEqual(graph["meta"]["topK"], 3)

    def test_top_k_is_capped_by_available_neighbors(self) -> None:
        graph = graph_module.build_graph(self.frame.iloc[:3], top_k=20)
        self.assertEqual(graph["meta"]["topK"], 2)
        self.assertTrue(all(len(items) == 2 for items in graph["recommendations"].values()))

    def test_output_is_deterministic(self) -> None:
        first = graph_module.build_graph(self.frame, top_k=4)
        second = graph_module.build_graph(self.frame.copy(), top_k=4)
        self.assertEqual(first, second)

    def test_rejects_too_few_tracks(self) -> None:
        with self.assertRaisesRegex(ValueError, "至少需要两首"):
            graph_module.build_graph(self.frame.iloc[:1], top_k=1)

    def test_rejects_duplicate_ids(self) -> None:
        duplicate = pd.concat([self.frame.iloc[:2], self.frame.iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "歌曲 ID"):
            graph_module.build_graph(duplicate, top_k=1)

    def test_rejects_missing_feature_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少必要字段"):
            graph_module.build_graph(self.frame.drop(columns=["mfcc_13"]), top_k=1)


if __name__ == "__main__":
    unittest.main()
