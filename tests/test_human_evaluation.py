from __future__ import annotations

import unittest

import pandas as pd

from tests.helpers import load_script


demo_module = load_script("00_generate_demo_data.py", "test_human_demo_module")
freeze_module = load_script("10_freeze_human_evaluation.py", "test_human_freeze_module")
score_module = load_script("11_score_human_evaluation.py", "test_human_score_module")


class HumanEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = demo_module.generate_demo(count=60, seed=9)
        self.frame["path"] = [f"data/raw/public/{index}.wav" for index in range(len(self.frame))]

    def build(self):
        return freeze_module.build_package(
            self.frame,
            query_count=12,
            top_k=3,
            seed=42,
        )

    def test_frozen_package_is_deterministic_and_blinded(self) -> None:
        first = self.build()
        second = self.build()
        for first_frame, second_frame in zip(first[:4], second[:4]):
            pd.testing.assert_frame_equal(first_frame, second_frame)

        pairs, playback, key, labels, manifest = first
        self.assertEqual(list(pairs.columns), ["pair_id", "presentation_order"])
        self.assertNotIn("method", playback.columns)
        self.assertNotIn("method", labels.columns)
        self.assertNotIn("query_id", labels.columns)
        self.assertEqual(len(key), 12 * 3 * 3)
        self.assertEqual(manifest["counts"]["queries"], 12)
        self.assertEqual(sum(manifest["query_genre_distribution"].values()), 12)

    def test_supports_compact_two_method_review(self) -> None:
        pairs, _, key, _, manifest = freeze_module.build_package(
            self.frame,
            query_count=6,
            top_k=3,
            seed=42,
            methods=("standardized_cosine", "random"),
        )
        self.assertEqual(set(key["method"]), {"standardized_cosine", "random"})
        self.assertEqual(len(key), 6 * 2 * 3)
        self.assertLessEqual(len(pairs), len(key))
        self.assertEqual(manifest["config"]["methods"], ["standardized_cosine", "random"])

    def test_scoring_requires_complete_labels_for_final_metric(self) -> None:
        pairs, _, key, labels, _ = self.build()
        empty_result = score_module.score(key, labels)
        self.assertFalse(empty_result["primary_metric_ready"])
        self.assertEqual(empty_result["labeled_pairs"], 0)

        partial = labels.iloc[:5].copy()
        partial["relevance"] = "1"
        partial_result = score_module.score(key, partial)
        self.assertFalse(partial_result["primary_metric_ready"])

        complete = labels.copy()
        complete["relevance"] = [str(index % 2) for index in range(len(complete))]
        result = score_module.score(key, complete)
        self.assertTrue(result["primary_metric_ready"])
        self.assertIn("standardized_cosine", result["methods"])
        self.assertGreater(result["methods"]["standardized_cosine"]["valid_label_coverage"], 0)

    def test_disagreement_requires_adjudication(self) -> None:
        _, _, key, labels, _ = self.build()
        pair_id = labels.iloc[0]["pair_id"]
        disagreement = pd.DataFrame(
            [
                {"pair_id": pair_id, "annotator_id": "a", "relevance": "0"},
                {"pair_id": pair_id, "annotator_id": "b", "relevance": "1"},
            ]
        )
        result = score_module.score(key, disagreement)
        self.assertEqual(result["agreement"]["unresolved_disagreements"], 1)
        self.assertFalse(result["primary_metric_ready"])


if __name__ == "__main__":
    unittest.main()
