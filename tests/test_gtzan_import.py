from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tests.helpers import load_script


gtzan_module = load_script("06_import_gtzan_features.py", "test_gtzan_module")


def fake_features() -> dict[str, float]:
    return {
        "tempo": 120.0,
        "rms": 0.1,
        "zcr": 0.02,
        "spectral_centroid": 1200.0,
        "spectral_rolloff": 2400.0,
        **{f"mfcc_{index}": float(index) for index in range(1, 14)},
    }


class GtzanImportTests(unittest.TestCase):
    def test_resolves_restored_root_genre_layout(self) -> None:
        with tempfile.TemporaryDirectory(dir=gtzan_module.PROJECT_ROOT) as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "jazz" / "jazz.00001.wav"
            audio_path.parent.mkdir(parents=True)
            audio_path.write_bytes(b"RIFF")

            with patch.object(gtzan_module, "GTZAN_ROOT", root):
                result = gtzan_module.resolve_gtzan_audio_path(audio_path.name, "jazz")

            self.assertEqual(result, str(audio_path.relative_to(gtzan_module.PROJECT_ROOT)))

    def test_extracts_restored_audio_with_common_feature_extractor(self) -> None:
        with tempfile.TemporaryDirectory(dir=gtzan_module.PROJECT_ROOT) as temp_dir:
            root = Path(temp_dir)
            for genre in ("blues", "rock"):
                path = root / genre / f"{genre}.00000.wav"
                path.parent.mkdir(parents=True)
                path.write_bytes(b"RIFF")

            with (
                patch.object(gtzan_module, "GTZAN_ROOT", root),
                patch.object(gtzan_module, "extract_audio_features", return_value=fake_features()),
            ):
                frame = gtzan_module.extract_gtzan_audio_features()

            self.assertEqual(len(frame), 2)
            self.assertEqual(set(frame["genre"]), {"blues", "rock"})
            self.assertEqual(set(frame["source"]), {"gtzan"})
            self.assertTrue(frame["path"].str.endswith(".wav").all())

    def test_import_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "features.csv"
            output_path = Path(temp_dir) / "output.csv"
            pd.DataFrame([{"filename": "x.wav", "label": "jazz"}]).to_csv(input_path, index=False)

            with self.assertRaisesRegex(ValueError, "缺少必要字段"):
                gtzan_module.import_gtzan_features(input_path, output_path)


if __name__ == "__main__":
    unittest.main()
