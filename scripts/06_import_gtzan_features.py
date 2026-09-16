from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common import (
    PROCESSED_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    ensure_directories,
    extract_audio_features,
    find_audio_files,
    write_csv,
)


GTZAN_ROOT = RAW_DIR / "gtzan"
GTZAN_30SEC_DEFAULT = GTZAN_ROOT / "features_30_sec.csv"
GTZAN_3SEC_DEFAULT = GTZAN_ROOT / "features_3_sec.csv"


def find_gtzan_audio_files() -> list[Path]:
    for audio_root in (GTZAN_ROOT / "genres_original", GTZAN_ROOT):
        audio_files = find_audio_files(audio_root)
        if audio_files:
            return audio_files
    return []


def resolve_gtzan_audio_path(filename: str, genre: str) -> str:
    candidates = [
        GTZAN_ROOT / "genres_original" / genre / filename,
        GTZAN_ROOT / genre / filename,
        GTZAN_ROOT / "genres_original" / filename,
        GTZAN_ROOT / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.relative_to(PROJECT_ROOT))
    return ""


def extract_gtzan_audio_features(limit: int | None = None) -> pd.DataFrame:
    audio_files = find_gtzan_audio_files()
    if limit:
        audio_files = audio_files[:limit]
    if not audio_files:
        raise FileNotFoundError(
            "找不到 GTZAN 音频。支持 data/raw/gtzan/<genre>/*.wav "
            "或 data/raw/gtzan/genres_original/<genre>/*.wav。"
        )

    rows = []
    for index, audio_path in enumerate(audio_files):
        genre = audio_path.parent.name
        try:
            features = extract_audio_features(audio_path)
        except Exception as exc:
            print(f"跳过 {audio_path.name}: {exc}")
            continue

        stable_name = audio_path.stem.replace(".", "_")
        rows.append(
            {
                "id": f"gtzan_{genre}_{stable_name}",
                "track_id": audio_path.stem,
                "title": audio_path.stem,
                "artist": "GTZAN",
                "genre": genre,
                "source": "gtzan",
                "filename": audio_path.name,
                "path": str(audio_path.relative_to(PROJECT_ROOT)),
                **features,
            }
        )
        print(f"已处理 GTZAN [{index + 1}/{len(audio_files)}]: {audio_path.name}")

    if not rows:
        raise RuntimeError("GTZAN 音频均无法提取特征。")
    return pd.DataFrame(rows)


def import_gtzan_features(
    input_csv: Path,
    output_csv: Path,
    limit: int | None = None,
) -> pd.DataFrame:
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
            "id": f"gtzan_{genre}_{filename.replace('.', '_')}",
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
        for mfcc_index in range(1, 14):
            item[f"mfcc_{mfcc_index}"] = row[f"mfcc{mfcc_index}_mean"]
        rows.append(item)

    result = pd.DataFrame(rows)
    write_csv(result, output_csv)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="从 GTZAN 音频或兼容 CSV 构建统一特征")
    parser.add_argument("--source", choices=["audio", "csv"], default="audio")
    parser.add_argument(
        "--input",
        type=Path,
        default=GTZAN_30SEC_DEFAULT,
        help="--source csv 时使用的 features_30_sec.csv 或 features_3_sec.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "gtzan_features.csv",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    ensure_directories()
    if args.source == "audio":
        result = extract_gtzan_audio_features(args.limit)
        write_csv(result, args.output)
    else:
        result = import_gtzan_features(args.input, args.output, args.limit)
    print(f"GTZAN 特征已生成: {args.output}")
    print(f"共处理 {len(result)} 条")


if __name__ == "__main__":
    main()
