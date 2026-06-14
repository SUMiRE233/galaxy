from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEB_DIR = PROJECT_ROOT / "web"

FEATURE_COLUMNS = [
    "id",
    "track_id",
    "title",
    "artist",
    "genre",
    "source",
    "filename",
    "path",
    "tempo",
    "rms",
    "zcr",
    "spectral_centroid",
    "spectral_rolloff",
    *[f"mfcc_{i}" for i in range(1, 14)],
]

NUMERIC_FEATURE_COLUMNS = [
    "tempo",
    "rms",
    "zcr",
    "spectral_centroid",
    "spectral_rolloff",
    *[f"mfcc_{i}" for i in range(1, 14)],
]

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}


def ensure_directories() -> None:
    for path in (
        RAW_DIR / "personal" / "audios",
        RAW_DIR / "fma_small",
        PROCESSED_DIR,
        WEB_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def empty_feature_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FEATURE_COLUMNS)


def normalize_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = "" if column not in NUMERIC_FEATURE_COLUMNS else np.nan
    return frame[FEATURE_COLUMNS]


def find_audio_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def extract_audio_features(audio_path: Path, duration: float = 30.0) -> dict[str, float]:
    try:
        import librosa
    except ImportError as exc:
        raise RuntimeError(
            "缺少 librosa。请先运行: pip install -r requirements.txt"
        ) from exc

    y, sr = librosa.load(audio_path, sr=None, mono=True, duration=duration)
    if y.size == 0:
        raise ValueError("音频为空或无法解码")

    tempo_result, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.asarray(tempo_result).reshape(-1)[0])
    rms = float(np.mean(librosa.feature.rms(y=y)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    features = {
        "tempo": tempo,
        "rms": rms,
        "zcr": zcr,
        "spectral_centroid": centroid,
        "spectral_rolloff": rolloff,
    }
    features.update({f"mfcc_{i + 1}": float(value) for i, value in enumerate(mfcc.mean(axis=1))})
    return features


def write_csv(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalize_feature_frame(frame).to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"已生成: {output_path.relative_to(PROJECT_ROOT)} ({len(frame)} 首)")


def first_nonempty(values: Iterable[object], default: str) -> str:
    for value in values:
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return default

