from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.helpers import load_script


server_module = load_script("server.py", "test_server_module")
client = TestClient(server_module.app)


class ServerTests(unittest.TestCase):
    def test_sanitize_filename_removes_parent_directories(self) -> None:
        self.assertEqual(server_module.sanitize_filename("../../unsafe song.mp3"), "unsafe song.mp3")

    def test_audio_endpoint_rejects_path_outside_project(self) -> None:
        with self.assertRaises(HTTPException) as context:
            server_module.get_audio("../outside.mp3")
        self.assertEqual(context.exception.status_code, 400)

    def test_upload_rejects_unsupported_extension(self) -> None:
        response = client.post(
            "/api/upload-personal",
            files={"file": ("notes.txt", b"not audio", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_enforces_size_limit(self) -> None:
        with patch.object(server_module, "MAX_UPLOAD_SIZE", 4):
            response = client.post(
                "/api/upload-personal",
                files={"file": ("sample.wav", b"12345", "audio/wav")},
            )
        self.assertEqual(response.status_code, 413)

    def test_unknown_genre_upload_enters_confirmation_flow(self) -> None:
        features = {
            "tempo": 120.0,
            "rms": 0.1,
            "zcr": 0.02,
            "spectral_centroid": 1200.0,
            "spectral_rolloff": 2400.0,
            **{f"mfcc_{index}": float(index) for index in range(1, 14)},
        }
        metadata = {
            "filename": "sample.wav",
            "title": "Synthetic Sample",
            "artist": "Test Artist",
            "album": "",
            "genre": "Unknown",
            "year": "",
            "track_number": "",
            "source_method": "filename",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with (
                patch.object(server_module, "PERSONAL_AUDIO_DIR", temp_path / "audio"),
                patch.object(server_module, "PENDING_PATH", temp_path / "pending.json"),
                patch.object(server_module, "read_audio_metadata", return_value=metadata),
                patch.object(server_module, "extract_audio_features", return_value=features),
            ):
                response = client.post(
                    "/api/upload-personal",
                    files={"file": ("sample.wav", b"synthetic", "audio/wav")},
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["need_genre"])
        self.assertIn("temp_id", response.json())

    def test_cancel_pending_upload_removes_record_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_dir = temp_path / "audio"
            audio_dir.mkdir()
            audio_path = audio_dir / "sample.wav"
            audio_path.write_bytes(b"synthetic")
            pending_path = temp_path / "pending.json"
            pending_path.write_text(
                json.dumps(
                    {
                        "pending_test": {
                            "metadata": {"filename": "sample.wav"},
                            "features": {},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server_module, "PERSONAL_AUDIO_DIR", audio_dir),
                patch.object(server_module, "PENDING_PATH", pending_path),
            ):
                response = client.delete("/api/pending-personal/pending_test")

            self.assertEqual(response.status_code, 200)
            self.assertFalse(audio_path.exists())
            self.assertEqual(json.loads(pending_path.read_text(encoding="utf-8")), {})

    def test_rebuild_request_validation_rejects_invalid_values(self) -> None:
        invalid_source = client.post("/api/rebuild-graph", json={"sources": ["invalid"]})
        invalid_top_k = client.post("/api/rebuild-graph", json={"top_k": 21})

        self.assertEqual(invalid_source.status_code, 422)
        self.assertEqual(invalid_top_k.status_code, 422)

    def test_export_contains_personal_metadata_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_dir = root / "audio"
            audio_dir.mkdir()
            (audio_dir / "sample.wav").write_bytes(b"audio")
            features_path = root / "personal_features.csv"
            tracks_path = root / "personal_tracks.csv"
            pending_path = root / "pending.json"
            pd.DataFrame(
                [
                    {
                        **{column: "" for column in server_module.FEATURE_COLUMNS},
                        "id": "personal_test",
                        "source": "personal",
                        "filename": "sample.wav",
                    }
                ]
            ).to_csv(features_path, index=False)
            pd.DataFrame([{"filename": "sample.wav", "title": "Sample"}]).to_csv(
                tracks_path,
                index=False,
            )

            with (
                patch.object(server_module, "PERSONAL_AUDIO_DIR", audio_dir),
                patch.object(server_module, "PERSONAL_FEATURES_PATH", features_path),
                patch.object(server_module, "PERSONAL_TRACKS_PATH", tracks_path),
                patch.object(server_module, "PENDING_PATH", pending_path),
            ):
                response = client.get("/api/personal/export")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["x-personal-track-count"], "1")
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"manifest.json", "personal_features.csv", "personal_tracks.csv", "audios/sample.wav"},
                )

    def test_delete_personal_track_removes_only_selected_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_dir = root / "audio"
            audio_dir.mkdir()
            (audio_dir / "remove.wav").write_bytes(b"remove")
            (audio_dir / "keep.wav").write_bytes(b"keep")
            features_path = root / "personal_features.csv"
            tracks_path = root / "personal_tracks.csv"
            pending_path = root / "pending.json"
            processed_dir = root / "processed"
            processed_dir.mkdir()
            rows = []
            for identifier, filename in (("personal_remove", "remove.wav"), ("personal_keep", "keep.wav")):
                rows.append(
                    {
                        **{column: "" for column in server_module.FEATURE_COLUMNS},
                        "id": identifier,
                        "source": "personal",
                        "filename": filename,
                    }
                )
            pd.DataFrame(rows).to_csv(features_path, index=False)
            pd.DataFrame(
                [{"filename": "remove.wav"}, {"filename": "keep.wav"}]
            ).to_csv(tracks_path, index=False)

            with (
                patch.object(server_module, "PERSONAL_AUDIO_DIR", audio_dir),
                patch.object(server_module, "PERSONAL_FEATURES_PATH", features_path),
                patch.object(server_module, "PERSONAL_TRACKS_PATH", tracks_path),
                patch.object(server_module, "PENDING_PATH", pending_path),
                patch.object(server_module, "PROCESSED_DIR", processed_dir),
                patch.object(server_module, "GRAPH_PATH", root / "web_graph.json"),
                patch.object(server_module, "rebuild_graph", return_value={"nodes": 1, "links": 0, "personal_count": 1}),
            ):
                response = client.delete("/api/personal/personal_remove")

            self.assertEqual(response.status_code, 200)
            self.assertFalse((audio_dir / "remove.wav").exists())
            self.assertTrue((audio_dir / "keep.wav").exists())
            remaining = pd.read_csv(features_path)
            self.assertEqual(remaining["id"].tolist(), ["personal_keep"])

    def test_reset_personal_data_removes_rows_audio_and_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_dir = root / "audio"
            audio_dir.mkdir()
            (audio_dir / "sample.wav").write_bytes(b"audio")
            features_path = root / "personal_features.csv"
            tracks_path = root / "personal_tracks.csv"
            pending_path = root / "pending.json"
            processed_dir = root / "processed"
            processed_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        **{column: "" for column in server_module.FEATURE_COLUMNS},
                        "id": "personal_test",
                        "source": "personal",
                        "filename": "sample.wav",
                    }
                ]
            ).to_csv(features_path, index=False)
            pd.DataFrame([{"filename": "sample.wav"}]).to_csv(tracks_path, index=False)
            pending_path.write_text("{}", encoding="utf-8")

            with (
                patch.object(server_module, "PERSONAL_AUDIO_DIR", audio_dir),
                patch.object(server_module, "PERSONAL_FEATURES_PATH", features_path),
                patch.object(server_module, "PERSONAL_TRACKS_PATH", tracks_path),
                patch.object(server_module, "PENDING_PATH", pending_path),
                patch.object(server_module, "PROCESSED_DIR", processed_dir),
                patch.object(server_module, "GRAPH_PATH", root / "web_graph.json"),
                patch.object(server_module, "rebuild_graph", return_value={"nodes": 30, "links": 94, "personal_count": 0}),
            ):
                response = client.post("/api/personal/reset")

            self.assertEqual(response.status_code, 200)
            self.assertFalse((audio_dir / "sample.wav").exists())
            self.assertTrue(pd.read_csv(features_path).empty)
            self.assertTrue(pd.read_csv(tracks_path).empty)
            self.assertEqual(json.loads(pending_path.read_text(encoding="utf-8")), {})


if __name__ == "__main__":
    unittest.main()
