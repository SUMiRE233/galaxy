from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import load_script


pipeline_module = load_script("05_run_pipeline.py", "test_pipeline_module")


class PipelineDetectionTests(unittest.TestCase):
    def test_gtzan_detection_accepts_restored_audio_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            audio_path = raw_dir / "gtzan" / "jazz" / "jazz.00001.wav"
            audio_path.parent.mkdir(parents=True)
            audio_path.write_bytes(b"RIFF")

            with patch.object(pipeline_module, "RAW_DIR", raw_dir):
                self.assertTrue(pipeline_module.has_gtzan_data())

    def test_gtzan_detection_accepts_compatible_feature_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            gtzan_dir = raw_dir / "gtzan"
            gtzan_dir.mkdir()
            (gtzan_dir / "features_3_sec.csv").write_text("filename\n", encoding="utf-8")

            with patch.object(pipeline_module, "RAW_DIR", raw_dir):
                self.assertTrue(pipeline_module.has_gtzan_data())

    def test_missing_sources_are_not_reported_as_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            with patch.object(pipeline_module, "RAW_DIR", raw_dir):
                self.assertFalse(pipeline_module.has_personal_data())
                self.assertFalse(pipeline_module.has_gtzan_data())


if __name__ == "__main__":
    unittest.main()
