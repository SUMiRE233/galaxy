from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from tests.helpers import load_script


annotation_module = load_script("13_serve_human_annotation.py", "test_annotation_module")


class AnnotationServerTests(unittest.TestCase):
    def test_state_is_blinded_and_label_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "package"
            package.mkdir()
            pd.DataFrame([{"pair_id": "pair_0001", "presentation_order": 1}]).to_csv(
                package / "pairs.csv", index=False
            )
            pd.DataFrame(
                [
                    {
                        "pair_id": "pair_0001",
                        "query_id": "secret_query",
                        "candidate_id": "secret_candidate",
                        "query_path": "data/raw/gtzan/a.wav",
                        "candidate_path": "data/raw/gtzan/b.wav",
                    }
                ]
            ).to_csv(package / "playback_index.csv", index=False)
            labels_path = root / "labels.csv"
            app = annotation_module.create_app(package, labels_path)
            client = TestClient(app)

            state = client.get("/api/state")
            self.assertEqual(state.status_code, 200)
            item = state.json()["items"][0]
            self.assertNotIn("query_id", item)
            self.assertNotIn("candidate_id", item)
            self.assertNotIn("method", item)

            response = client.post(
                "/api/label",
                json={
                    "pair_id": "pair_0001",
                    "relevance": "1",
                    "confidence": 3,
                    "notes": "clear timbre and rhythm",
                },
            )
            self.assertEqual(response.status_code, 200)
            labels = pd.read_csv(labels_path)
            self.assertEqual(len(labels), 1)
            self.assertEqual(str(labels.iloc[0]["relevance"]), "1")
            self.assertEqual(labels.iloc[0]["annotator_id"], "annotator_1")

    def test_rejects_unknown_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "package"
            package.mkdir()
            pd.DataFrame([{"pair_id": "pair_0001", "presentation_order": 1}]).to_csv(
                package / "pairs.csv", index=False
            )
            pd.DataFrame(
                [
                    {
                        "pair_id": "pair_0001",
                        "query_id": "q",
                        "candidate_id": "c",
                        "query_path": "data/raw/gtzan/a.wav",
                        "candidate_path": "data/raw/gtzan/b.wav",
                    }
                ]
            ).to_csv(package / "playback_index.csv", index=False)
            client = TestClient(annotation_module.create_app(package, root / "labels.csv"))
            response = client.post(
                "/api/label",
                json={"pair_id": "unknown", "relevance": "0", "confidence": 2},
            )
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
