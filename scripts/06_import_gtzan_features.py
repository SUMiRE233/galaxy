from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common import PROCESSED_DIR, ensure_directories, write_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GTZAN_30SEC_DEFAULT = PROJECT_ROOT / "data" / "raw" / "gtzan" / "features_30_sec.csv"
GTZAN_3SEC_DEFAULT = PROJECT_ROOT / "data" / "raw" / "gtzan" / "features_3_sec.csv"
GTZAN_AUDIO_ROOT = PROJECT_ROOT / "data" / "raw" / "gtzan" / "genres_original"


def resolve_gtzan_audio_path(filename: str, genre: str) -> str:
    """Return a project-relative audio path when the GTZAN wav exists locally."""
    candidates = [
        GTZAN_AUDIO_ROOT / genre / filename,
        GTZAN_AUDIO_ROOT / filename,
        PROJECT_ROOT / "data" / "raw" / "gtzan" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.relative_to(PROJECT_ROOT))
    return ""


def import_gtzan_features(input_csv: Path, output_csv: Path, limit: int | None = None) -> pd.DataFrame:
    if not input_csv.exists():
        raise FileNotFoundError(f"找不到 GTZAN 特征文件: {input_csv}")

    df = pd.read_csv(input_csv)

    required = {
        "filename",
        "label",
        "tempo",
        "rms_mean",
        "zero_crossing_rate_mean",
        "spectral_centroid_mean",
        "rolloff_mean",
    } | {f"mfcc{i}_mean" for i in range(1, 14)}

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"GTZAN 特征文件缺少必要字段: {sorted(missing)}")

    if limit:
        df = df.head(limit)

    rows = []
    for index, row in df.iterrows():
        filename = str(row["filename"])
        genre = str(row["label"])

        item = {
            "id": f"gtzan_{index:05d}",
            "track_id": filename.replace(".", "_"),
            "title": filename,
            "artist": "GTZAN",
            "genre": genre,
            "source": "gtzan",
            "filename": filename,
            "path": resolve_gtzan_audio_path(filename, genre),
            "tempo": row["tempo"],
            "rms": row["rms_mean"],
            "zcr": row["zero_crossing_rate_mean"],
            "spectral_centroid": row["spectral_centroid_mean"],
            "spectral_rolloff": row["rolloff_mean"],
        }

        for i in range(1, 14):
            item[f"mfcc_{i}"] = row[f"mfcc{i}_mean"]

        rows.append(item)

    result = pd.DataFrame(rows)
    write_csv(result, output_csv)
    print(f"GTZAN 特征已导入: {output_csv}")
    print(f"共导入 {len(result)} 条")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 GTZAN 预计算特征")
    parser.add_argument(
        "--input",
        type=Path,
        default=GTZAN_30SEC_DEFAULT,
        help="GTZAN features_30_sec.csv 或 features_3_sec.csv 路径",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "gtzan_features.csv",
        help="输出 CSV 路径",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    ensure_directories()
    import_gtzan_features(args.input, args.output, args.limit)


if __name__ == "__main__":
    main()
